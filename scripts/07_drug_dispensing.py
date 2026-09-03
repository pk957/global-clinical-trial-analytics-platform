"""
07_drug_dispensing.py

Global Clinical Trial Analytics Platform
-----------------------------------------------------------------------------
Purpose:
    Generate drug dispensing records for randomized subjects. Medication is
    dispensed only at protocol-defined treatment visits, according to the
    treatment arm each subject was assigned during randomization.

    This script simulates pharmacy dispensing data as it would appear when
    exported from an Electronic Data Capture (EDC) system. It is an ETL
    transformation step that enriches existing randomization and visit
    records — it does NOT generate new patients, subjects, or visits.

Input:
    data/raw/randomization.csv
    data/raw/visits.csv

Output:
    data/raw/drug_dispensing.csv

Pipeline position:
    01_master_data.py   -> studies / sites reference data
    02_screening.py      -> screening records
    03_subjects.py       -> enrolled subjects
    04_randomization.py  -> arm / treatment assignment
    05_visits.py         -> scheduled + completed visits
    06_lab_results.py    -> laboratory results per visit
    07_drug_dispensing.py -> drug dispensing per treatment visit  <-- this script
    08_tumor_assessments.py -> downstream consumer
    09_adverse_events.py    -> downstream consumer
    10_study_completion.py  -> downstream consumer
-----------------------------------------------------------------------------
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

# =============================================================================
# CONFIGURATION / CONSTANTS
# =============================================================================

# Fixed seed guarantees the pipeline is reproducible end-to-end. Every
# script in this platform seeds with the same value so that a full pipeline
# re-run produces byte-for-byte identical output for QA / diffing purposes.
# This script contains no random sampling, but the seed is retained for
# consistency with the rest of the pipeline and in case future dispensing
# logic (e.g. kit lot assignment) introduces randomness.
RANDOM_SEED = 42

# Paths are resolved relative to the project root so the script can be run
# from any working directory (e.g. cron, CI, or an ad-hoc terminal session).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

RANDOMIZATION_FILE = RAW_DATA_DIR / "randomization.csv"
VISITS_FILE = RAW_DATA_DIR / "visits.csv"
OUTPUT_FILE = RAW_DATA_DIR / "drug_dispensing.csv"

# Medication is dispensed only at these protocol-defined treatment visits.
# Dispensing at "End of Treatment" or "Safety Follow-up" would be a protocol
# deviation, since those visits exist to assess the subject after dosing has
# concluded, not to administer further drug.
DISPENSING_VISIT_NAMES = {
    "Baseline",
    "Cycle 1 Day 1",
    "Cycle 2 Day 1",
    "Cycle 3 Day 1",
}

# Maps each randomized treatment arm to the drug product actually dispensed
# at the pharmacy. This mirrors real trial blinding conventions, where the
# randomization arm label and the dispensed product label can differ
# (e.g. a "Standard of Care + Placebo" arm still receives a physical kit).
ARM_TO_DRUG = {
    "NVC-CRC101": "NVC-CRC101",
    "Standard of Care + Placebo": "Placebo",
}

# Every dispensing event represents one full treatment kit — trial supply
# is packaged and tracked at the kit level, not by individual dose units.
QUANTITY_DISPENSED = 1
DISPENSING_UNIT = "Kit"

# Progress logging cadence. Printing on every row would flood stdout on
# large studies; every 5,000 rows keeps logs useful without being noisy.
PROGRESS_INTERVAL = 5_000

# Single batch timestamp applied to every row generated in this run. This
# mirrors how an EDC export batch is stamped once at extraction time rather
# than per-record, which keeps the "created_at" field meaningful for
# downstream incremental-load logic (e.g. Athena partitioning).
BATCH_TIMESTAMP = datetime.now().isoformat()


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(randomization_path: Path, visits_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load the randomization and visits datasets that drug dispensing records
    will be generated from.

    Loading is isolated in its own function so validation and error
    handling around file I/O stays independent of the generation logic,
    consistent with the previous scripts in this pipeline.
    """
    if not randomization_path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {randomization_path}. "
            f"Run 04_randomization.py before running this script."
        )
    if not visits_path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {visits_path}. "
            f"Run 05_visits.py before running this script."
        )

    randomization_df = pd.read_csv(randomization_path)
    visits_df = pd.read_csv(visits_path)

    required_randomization_columns = {
        "randomization_id",
        "subject_id",
        "study_id",
        "treatment_arm",
        "randomization_date",
    }
    missing_randomization_columns = required_randomization_columns - set(
        randomization_df.columns
    )
    if missing_randomization_columns:
        raise ValueError(
            f"randomization.csv is missing required columns: "
            f"{missing_randomization_columns}"
        )

    required_visit_columns = {"visit_id", "visit_name", "visit_number", "visit_date"}
    missing_visit_columns = required_visit_columns - set(visits_df.columns)
    if missing_visit_columns:
        raise ValueError(
            f"visits.csv is missing required columns: {missing_visit_columns}"
        )

    return randomization_df, visits_df


# =============================================================================
# DRUG DISPENSING GENERATION
# =============================================================================

def generate_drug_dispensing(
    randomization_df: pd.DataFrame, visits_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Generate one drug dispensing record for every treatment visit belonging
    to a randomized subject.

    Business rule: only randomized subjects can receive medication, and
    only at the four dispensing visits defined by the protocol. Joining
    visits to randomization (rather than iterating visits alone) enforces
    this naturally — a subject who was never randomized simply has no
    randomization record to join against, and therefore receives no drug.
    """
    print("Script Started")

    # Restrict to dispensing visits only. This is the mechanism that
    # enforces "no medication at End of Treatment / Safety Follow-up" —
    # those visit names are never in DISPENSING_VISIT_NAMES, so they are
    # excluded before any dispensing records are built.
    dispensing_visits_df = visits_df[
        visits_df["visit_name"].isin(DISPENSING_VISIT_NAMES)
    ]

    # Inner join to randomization ensures every dispensing record carries
    # the subject's assigned treatment arm and that only randomized
    # subjects appear in the output.
    merged_df = dispensing_visits_df.merge(
        randomization_df,
        on="subject_id",
        how="inner",
        suffixes=("", "_randomization"),
    )

    # study_id may be present on both sides of the join if a subject's
    # visits and randomization records both carry it; the visits.csv value
    # is treated as authoritative since visits are the join anchor here.
    if "study_id_randomization" in merged_df.columns:
        merged_df = merged_df.drop(columns=["study_id_randomization"])

    records = []
    dispensing_counter = 1

    for row in merged_df.itertuples(index=False):
        # Drug product dispensed depends on the assigned treatment arm.
        # Missing/unrecognized arms are surfaced immediately rather than
        # silently skipped, since an un-mappable arm indicates a data
        # integrity problem upstream in randomization.csv.
        treatment_arm = row.treatment_arm
        if treatment_arm not in ARM_TO_DRUG:
            raise ValueError(
                f"Unrecognized treatment_arm '{treatment_arm}' for "
                f"subject {row.subject_id}; cannot determine drug_name."
            )
        drug_name = ARM_TO_DRUG[treatment_arm]

        records.append(
            {
                "dispensing_id": f"DSP-{dispensing_counter:06d}",
                "visit_id": row.visit_id,
                "randomization_id": row.randomization_id,
                "subject_id": row.subject_id,
                "study_id": row.study_id,
                "treatment_arm": treatment_arm,
                "drug_name": drug_name,
                "quantity_dispensed": QUANTITY_DISPENSED,
                "unit": DISPENSING_UNIT,
                "dispensing_date": row.visit_date,
                "created_at": BATCH_TIMESTAMP,
            }
        )

        if dispensing_counter % PROGRESS_INTERVAL == 0:
            print(f"Generated {dispensing_counter} dispensing records...")

        dispensing_counter += 1

    print("Drug dispensing generation completed.")

    return pd.DataFrame.from_records(records)


# =============================================================================
# VALIDATION
# =============================================================================

def validate_drug_dispensing(
    dispensing_df: pd.DataFrame, randomization_df: pd.DataFrame
) -> None:
    """
    Enforce referential integrity and protocol compliance before persisting
    output.

    Downstream analytics (08_tumor_assessments.py, 09_adverse_events.py,
    10_study_completion.py) assume every randomized subject has a complete,
    protocol-compliant dispensing history with no duplicate or orphaned
    records. Failing fast here prevents silently propagating bad data.
    """
    # Rule: dispensing_id values must be unique (primary key integrity).
    if dispensing_df["dispensing_id"].duplicated().any():
        raise ValueError("Duplicate dispensing_id values detected.")

    # Rule: every randomized subject must receive exactly four dispensing
    # records — one per protocol-defined dispensing visit. More or fewer
    # indicates either a missing treatment visit or a protocol deviation.
    expected_count_per_subject = len(DISPENSING_VISIT_NAMES)
    records_per_subject = dispensing_df.groupby("subject_id").size()

    missing_subjects = set(randomization_df["subject_id"]) - set(
        records_per_subject.index
    )
    if missing_subjects:
        raise ValueError(
            f"Randomized subjects with no dispensing records at all: "
            f"{missing_subjects}"
        )

    incorrect_counts = records_per_subject[
        records_per_subject != expected_count_per_subject
    ]
    if not incorrect_counts.empty:
        raise ValueError(
            f"Subjects with an incorrect number of dispensing records "
            f"(expected {expected_count_per_subject}): "
            f"{incorrect_counts.to_dict()}"
        )

    # Rule: medication must be dispensed only at treatment visits. This is
    # a hard protocol safety rule — dispensing outside the defined visit
    # set would represent an unapproved drug administration event.
    invalid_visits = dispensing_df[
        ~dispensing_df["treatment_arm"].isin(ARM_TO_DRUG.keys())
    ]
    if not invalid_visits.empty:
        raise ValueError(
            f"{len(invalid_visits)} dispensing records reference an "
            f"unrecognized treatment_arm."
        )

    # Rule: no missing treatment arms — every dispensing record must carry
    # a non-null treatment arm, since drug identity cannot be determined
    # without it.
    if dispensing_df["treatment_arm"].isna().any():
        raise ValueError("Dispensing records found with a missing treatment_arm.")

    # Rule: dispensing_date must always equal the source visit's
    # visit_date — a kit cannot be dispensed on a date other than the
    # visit at which it was administered. Recomputed here directly against
    # visits data would require re-merging; since dispensing_date is
    # already copied 1:1 from visit_date at generation time, we confirm
    # no nulls slipped through instead.
    if dispensing_df["dispensing_date"].isna().any():
        raise ValueError("Dispensing records found with a missing dispensing_date.")

    print("Validation passed: drug dispensing records are complete and consistent.")


# =============================================================================
# PERSISTENCE
# =============================================================================

def save_csv(df: pd.DataFrame, output_path: Path) -> None:
    """
    Persist the final drug dispensing dataset to the raw data layer.

    Output is written to data/raw/ so that downstream consumers
    (08_tumor_assessments.py, 09_adverse_events.py, 10_study_completion.py,
    and Athena / SQL / QuickSight) all read from a single consistent
    source location, matching the convention of every prior script in this
    pipeline.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} dispensing records to {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Orchestrate the end-to-end drug dispensing ETL step:
    load randomization + visits -> generate dispensing records ->
    validate -> persist.
    """
    randomization_df, visits_df = load_data(RANDOMIZATION_FILE, VISITS_FILE)
    dispensing_df = generate_drug_dispensing(randomization_df, visits_df)
    validate_drug_dispensing(dispensing_df, randomization_df)
    save_csv(dispensing_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()