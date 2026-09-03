"""
06_lab_results.py

Global Clinical Trial Analytics Platform
-----------------------------------------------------------------------------
Purpose:
    Generate laboratory test results collected during scheduled protocol
    visits. Each visit that occurred receives exactly one result for each
    of the six required laboratory parameters defined by the protocol.

    This script simulates laboratory data as it would appear when exported
    from an Electronic Data Capture (EDC) system. It is an ETL transformation
    step that enriches existing visit records — it does NOT generate new
    patients, subjects, or visits.

Input:
    data/raw/visits.csv

Output:
    data/raw/laboratory_results.csv

Pipeline position:
    01_master_data.py   -> studies / sites reference data
    02_screening.py     -> screening records
    03_subjects.py      -> enrolled subjects
    04_randomization.py -> arm / treatment assignment
    05_visits.py        -> scheduled + completed visits
    06_lab_results.py   -> laboratory results per visit   <-- this script
-----------------------------------------------------------------------------
"""

import random
from datetime import datetime
from pathlib import Path

import pandas as pd

# =============================================================================
# CONFIGURATION / CONSTANTS
# =============================================================================

# Fixed seed guarantees the pipeline is reproducible end-to-end. Every
# script in this platform seeds with the same value so that a full pipeline
# re-run produces byte-for-byte identical output for QA / diffing purposes.
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Paths are resolved relative to the project root so the script can be run
# from any working directory (e.g. cron, CI, or an ad-hoc terminal session).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

INPUT_FILE = RAW_DATA_DIR / "visits.csv"
OUTPUT_FILE = RAW_DATA_DIR / "laboratory_results.csv"

# The protocol requires the same six-panel lab draw at every scheduled visit
# for safety monitoring purposes. Each tuple defines:
#   (lab_test_name, unit, reference_low, reference_high)
# Reference ranges reflect typical adult clinical laboratory normals and are
# used both to generate plausible values and to compute the result_flag.
LAB_TESTS = [
    ("Hemoglobin", "g/dL", 11.5, 16.5),
    ("White Blood Cells", "x10^9/L", 4.0, 11.0),
    ("Platelets", "x10^9/L", 150, 450),
    ("ALT", "U/L", 10, 45),
    ("AST", "U/L", 10, 40),
    ("Creatinine", "mg/dL", 0.6, 1.3),
]

# Progress logging cadence. Printing on every row would flood stdout on
# large studies; every 10,000 rows keeps logs useful without being noisy.
PROGRESS_INTERVAL = 10_000

# Single batch timestamp applied to every row generated in this run. This
# mirrors how an EDC export batch is stamped once at extraction time rather
# than per-record, which keeps the "created_at" field meaningful for
# downstream incremental-load logic (e.g. Athena partitioning).
BATCH_TIMESTAMP = datetime.now().isoformat()


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(input_path: Path) -> pd.DataFrame:
    """
    Load the visits dataset that laboratory results will be generated for.

    Loading is isolated in its own function so validation and error
    handling around file I/O stays independent of the generation logic,
    consistent with the previous scripts in this pipeline.
    """
    if not input_path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {input_path}. "
            f"Run 05_visits.py before running this script."
        )

    visits_df = pd.read_csv(input_path)

    required_columns = {
        "visit_id",
        "subject_id",
        "study_id",
        "visit_number",
        "visit_name",
        "visit_date",
    }
    missing_columns = required_columns - set(visits_df.columns)
    if missing_columns:
        raise ValueError(
            f"visits.csv is missing required columns: {missing_columns}"
        )

    return visits_df


# =============================================================================
# LABORATORY GENERATION
# =============================================================================

def calculate_flag(value: float, reference_low: float, reference_high: float) -> str:
    """
    Classify a laboratory result against its reference range.

    Clinical trial safety review depends on flagging out-of-range values
    (Low / High) so that investigators and monitors can triage abnormal
    labs without manually comparing every value to its reference range.
    """
    if value < reference_low:
        return "Low"
    if value > reference_high:
        return "High"
    return "Normal"


def _generate_subject_baseline(reference_low: float, reference_high: float) -> float:
    """
    Establish a subject-specific baseline value within (and slightly around)
    the normal reference range.

    Real subjects have a personal physiological baseline — two people with
    "normal" hemoglobin still differ from each other. Anchoring each
    subject to their own baseline (rather than drawing every visit
    independently from the full range) avoids implausible subject-to-subject
    noise and sets up realistic longitudinal variation.
    """
    midpoint = (reference_low + reference_high) / 2
    spread = (reference_high - reference_low) / 2
    # Bias baseline generation toward the middle of the range using a
    # triangular distribution, since most healthy/enrolled subjects cluster
    # near clinical normal rather than at the extremes.
    return random.triangular(
        reference_low - spread * 0.1,
        reference_high + spread * 0.1,
        midpoint,
    )


def generate_lab_results(visits_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate exactly six laboratory results for every visit in the input.

    Business rule: laboratory values must show slight, clinically realistic
    biological variation between visits for the same subject rather than
    being fully independent draws each time. This is achieved by anchoring
    each subject to a per-parameter baseline and applying small,
    bounded fluctuations at each subsequent visit.
    """
    print("Script Started")

    records = []
    lab_result_counter = 1

    # Cache one baseline per (subject_id, lab_test) so repeat visits for the
    # same subject fluctuate around a consistent personal baseline instead
    # of drifting randomly, matching real longitudinal lab behavior.
    subject_baselines = {}

    for visit in visits_df.itertuples(index=False):
        for lab_test, unit, reference_low, reference_high in LAB_TESTS:
            baseline_key = (visit.subject_id, lab_test)

            if baseline_key not in subject_baselines:
                subject_baselines[baseline_key] = _generate_subject_baseline(
                    reference_low, reference_high
                )

            baseline_value = subject_baselines[baseline_key]

            # Small visit-to-visit fluctuation (+/- 4% of the reference
            # range width) simulates normal biological variability without
            # producing clinically implausible swings between visits.
            range_width = reference_high - reference_low
            fluctuation = random.uniform(-0.04, 0.04) * range_width
            result_value = round(baseline_value + fluctuation, 2)

            result_flag = calculate_flag(result_value, reference_low, reference_high)

            records.append(
                {
                    "lab_result_id": f"LAB-{lab_result_counter:06d}",
                    "visit_id": visit.visit_id,
                    "subject_id": visit.subject_id,
                    "study_id": visit.study_id,
                    "lab_test": lab_test,
                    "result_value": result_value,
                    "unit": unit,
                    "reference_low": reference_low,
                    "reference_high": reference_high,
                    "result_flag": result_flag,
                    "collection_date": visit.visit_date,
                    "created_at": BATCH_TIMESTAMP,
                }
            )

            if lab_result_counter % PROGRESS_INTERVAL == 0:
                print(f"Generated {lab_result_counter} laboratory results...")

            lab_result_counter += 1

    print("Laboratory results generation completed.")

    return pd.DataFrame.from_records(records)


# =============================================================================
# VALIDATION
# =============================================================================

def validate_lab_results(lab_df: pd.DataFrame, visits_df: pd.DataFrame) -> None:
    """
    Enforce referential integrity and completeness before persisting output.

    Downstream analytics (Athena / SQL / QuickSight) assume every visit has
    a complete six-parameter lab panel with no duplicate or orphaned
    records. Failing fast here prevents silently propagating bad data.
    """
    expected_tests = {test_name for test_name, _, _, _ in LAB_TESTS}
    expected_total = len(visits_df) * len(LAB_TESTS)

    # Rule: total row count must equal visits * 6.
    if len(lab_df) != expected_total:
        raise ValueError(
            f"Expected {expected_total} laboratory results "
            f"({len(visits_df)} visits x {len(LAB_TESTS)} tests), "
            f"got {len(lab_df)}."
        )

    # Rule: lab_result_id values must be unique (primary key integrity).
    if lab_df["lab_result_id"].duplicated().any():
        raise ValueError("Duplicate lab_result_id values detected.")

    # Rule: every visit must have exactly six results, no more, no fewer.
    results_per_visit = lab_df.groupby("visit_id").size()
    if not (results_per_visit == len(LAB_TESTS)).all():
        bad_visits = results_per_visit[results_per_visit != len(LAB_TESTS)]
        raise ValueError(
            f"Visits with incorrect lab result counts detected: "
            f"{bad_visits.to_dict()}"
        )

    # Rule: no missing laboratory parameters — every visit must contain all
    # six protocol-defined lab_test values, not just six results of any kind.
    tests_per_visit = lab_df.groupby("visit_id")["lab_test"].apply(set)
    incomplete_visits = tests_per_visit[tests_per_visit != expected_tests]
    if not incomplete_visits.empty:
        raise ValueError(
            f"Visits missing required lab parameters: "
            f"{list(incomplete_visits.index)}"
        )

    # Rule: collection_date must always match the source visit_date —
    # a lab result cannot be collected on a date other than the visit itself.
    merged = lab_df.merge(
        visits_df[["visit_id", "visit_date"]], on="visit_id", how="left"
    )
    mismatched = merged[merged["collection_date"] != merged["visit_date"]]
    if not mismatched.empty:
        raise ValueError(
            f"{len(mismatched)} laboratory results have a collection_date "
            f"that does not match their visit's visit_date."
        )

    print("Validation passed: laboratory results are complete and consistent.")


# =============================================================================
# PERSISTENCE
# =============================================================================

def save_csv(df: pd.DataFrame, output_path: Path) -> None:
    """
    Persist the final laboratory results dataset to the raw data layer.

    Output is written to data/raw/ so that downstream consumers (Athena
    external tables, SQL loads, QuickSight datasets) all read from a single
    consistent source location, matching the convention of every prior
    script in this pipeline.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} laboratory results to {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Orchestrate the end-to-end lab results ETL step:
    load visits -> generate lab results -> validate -> persist.
    """
    visits_df = load_data(INPUT_FILE)
    lab_results_df = generate_lab_results(visits_df)
    validate_lab_results(lab_results_df, visits_df)
    save_csv(lab_results_df, OUTPUT_FILE)


if __name__ == "__main__":
    main()