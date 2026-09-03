"""
08_tumor_assessments.py

Generates longitudinal tumor assessment records for randomized subjects
in the Global Clinical Trial Analytics Platform (Study CRC-GLB-301).
Reads randomization.csv and visits.csv from data/raw/ and writes
tumor_assessments.csv.

Tumor assessments simulate imaging evaluations performed at scheduled
study visits and are classified using RECIST 1.1-inspired response
categories. Each subject's measurements evolve from their own baseline
tumor size, and the treatment arm influences the simulated clinical
outcome -- this is what makes the resulting dataset usable downstream
for Overall Response Rate (ORR), Disease Control Rate (DCR), response
by treatment arm, and waterfall plot analytics.

Input
-----
data/raw/randomization.csv
data/raw/visits.csv

Output
------
data/raw/tumor_assessments.csv

Author: Senior Data Engineering Team
"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------
# Configuration / Constants
# --------------------------------------------------------------------------

RANDOM_SEED = 42

INPUT_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/raw")

# Tumor assessments occur only at the three imaging time points defined
# by the protocol's schedule of assessments -- Cycle 1 Day 1, Cycle 3
# Day 1, and Safety Follow-up are dosing/safety visits, not imaging
# visits, so they are deliberately excluded here.
TUMOR_ASSESSMENT_VISIT_NAMES = [
    "Baseline",
    "Cycle 2 Day 1",
    "End of Treatment",
]

TREATMENT_ARM_ACTIVE = "NVC-CRC101"

BASELINE_SIZE_MIN_MM = 40.0
BASELINE_SIZE_MAX_MM = 120.0

# Reduction/change ranges below encode the clinical hypothesis under
# test: the investigational product should outperform the comparator.
# Modeling the active arm with a stronger, more consistent shrinkage
# trend (and the comparator with a much smaller or even negative
# trend) is what allows downstream ORR/DCR analyses to show a credible
# treatment effect rather than two indistinguishable arms.
ACTIVE_ARM_CYCLE2_REDUCTION_RANGE = (0.10, 0.35)
ACTIVE_ARM_EOT_REDUCTION_RANGE = (0.20, 0.60)

PLACEBO_ARM_CYCLE2_REDUCTION_RANGE = (0.00, 0.10)
PLACEBO_ARM_EOT_CHANGE_RANGE = (-0.05, 0.20)

# RECIST 1.1-inspired thresholds for classifying tumor response from a
# subject's percent change in tumor size relative to their own
# baseline. These thresholds are what let a purely numeric measurement
# be rolled up into a clinically meaningful response category.
PR_THRESHOLD_PERCENT = -30.0
PD_THRESHOLD_PERCENT = 20.0

RESPONSE_CR = "Complete Response (CR)"
RESPONSE_PR = "Partial Response (PR)"
RESPONSE_SD = "Stable Disease (SD)"
RESPONSE_PD = "Progressive Disease (PD)"

PROGRESS_INTERVAL = 5000


# --------------------------------------------------------------------------
# Data Loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the randomization and visits datasets from the raw data directory."""
    randomization_df = pd.read_csv(input_dir / "randomization.csv")
    visits_df = pd.read_csv(input_dir / "visits.csv")
    return randomization_df, visits_df


# --------------------------------------------------------------------------
# Tumor Assessment Generation
# --------------------------------------------------------------------------

def calculate_response_category(tumor_size_mm: float, percent_change: float) -> str:
    """Classify a tumor assessment using simplified RECIST 1.1 rules.

    Categories are evaluated in clinical priority order: a tumor size
    of zero is unambiguously a Complete Response regardless of the
    exact percent change, so it is checked first; the remaining
    thresholds then partition the percent-change axis into
    progression, response, and stable disease.
    """
    if tumor_size_mm <= 0:
        return RESPONSE_CR
    if percent_change <= PR_THRESHOLD_PERCENT:
        return RESPONSE_PR
    if percent_change >= PD_THRESHOLD_PERCENT:
        return RESPONSE_PD
    return RESPONSE_SD


def _simulate_measurement(
    baseline_size_mm: float, treatment_arm: str, visit_name: str
) -> float:
    """Simulate a single post-baseline tumor measurement.

    Measurements are derived as a percentage change applied to the
    subject's own baseline (never redrawn independently) so that a
    subject's tumor trajectory reads as a plausible progression over
    time rather than a set of unrelated random numbers.
    """
    is_active_arm = treatment_arm == TREATMENT_ARM_ACTIVE

    if visit_name == "Cycle 2 Day 1":
        reduction_range = (
            ACTIVE_ARM_CYCLE2_REDUCTION_RANGE
            if is_active_arm
            else PLACEBO_ARM_CYCLE2_REDUCTION_RANGE
        )
        reduction = random.uniform(*reduction_range)
        measured_size = baseline_size_mm * (1 - reduction)

    elif visit_name == "End of Treatment":
        if is_active_arm:
            reduction = random.uniform(*ACTIVE_ARM_EOT_REDUCTION_RANGE)
            measured_size = baseline_size_mm * (1 - reduction)
        else:
            change = random.uniform(*PLACEBO_ARM_EOT_CHANGE_RANGE)
            measured_size = baseline_size_mm * (1 + change)

    else:
        raise ValueError(f"Unsupported post-baseline visit_name: {visit_name}")

    # A tumor measurement can never be physically negative.
    return max(measured_size, 0.0)


def generate_tumor_assessments(
    randomization_df: pd.DataFrame, visits_df: pd.DataFrame
) -> pd.DataFrame:
    """Generate one tumor assessment for each eligible imaging visit."""

    # A single batch timestamp reflects that this represents one tumor
    # assessment data extract/export, not per-row collection events.
    created_at = datetime.now().isoformat()

    # Tumor size trajectories are driven by treatment arm, so the arm
    # assigned at randomization must be joined onto each visit before
    # any measurements can be simulated.
    visits_with_arm = visits_df.merge(
        randomization_df[["randomization_id", "treatment_arm"]],
        on="randomization_id",
        how="left",
    )

    # Restrict to the three imaging time points defined by the protocol,
    # then keep each subject's visits in chronological order so the
    # baseline is always processed before Cycle 2 and End of Treatment.
    imaging_visits = visits_with_arm[
        visits_with_arm["visit_name"].isin(TUMOR_ASSESSMENT_VISIT_NAMES)
    ].sort_values(["subject_id", "visit_number"])

    total_assessments = len(imaging_visits)
    assessment_counter = 0

    # Each subject's baseline tumor size is generated once and then
    # reused for every subsequent assessment for that subject.
    subject_baselines: dict[str, float] = {}

    rows = []
    for _, visit_row in imaging_visits.iterrows():
        assessment_counter += 1

        subject_id = visit_row["subject_id"]
        treatment_arm = visit_row["treatment_arm"]
        visit_name = visit_row["visit_name"]

        if visit_name == "Baseline":
            tumor_size_mm = round(
                random.uniform(BASELINE_SIZE_MIN_MM, BASELINE_SIZE_MAX_MM), 1
            )
            subject_baselines[subject_id] = tumor_size_mm
            percent_change = 0.0
        else:
            baseline_size_mm = subject_baselines[subject_id]
            measured_size = _simulate_measurement(
                baseline_size_mm, treatment_arm, visit_name
            )
            tumor_size_mm = round(measured_size, 1)
            percent_change = round(
                (tumor_size_mm - baseline_size_mm) / baseline_size_mm * 100, 1
            )

        response_category = calculate_response_category(tumor_size_mm, percent_change)

        rows.append(
            {
                "assessment_id": f"TUM-{assessment_counter:06d}",
                "visit_id": visit_row["visit_id"],
                "randomization_id": visit_row["randomization_id"],
                "subject_id": subject_id,
                "study_id": visit_row["study_id"],
                "assessment_date": visit_row["visit_date"],
                "tumor_size_mm": tumor_size_mm,
                "percent_change_from_baseline": percent_change,
                "response_category": response_category,
                "created_at": created_at,
            }
        )

        if assessment_counter % PROGRESS_INTERVAL == 0:
            print(
                f"Generated {assessment_counter:>6} / {total_assessments} "
                "tumor assessments..."
            )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_tumor_assessments(
    randomization_df: pd.DataFrame,
    visits_df: pd.DataFrame,
    tumor_assessments_df: pd.DataFrame,
) -> None:
    """Run referential integrity and business-rule checks on the output."""

    # assessment_id must be globally unique so downstream Athena/SQL
    # queries can safely use it as a primary key.
    assert tumor_assessments_df["assessment_id"].is_unique, (
        "Duplicate assessment_id detected."
    )

    # Every randomized subject must have exactly three tumor
    # assessments (Baseline, Cycle 2 Day 1, End of Treatment); a
    # missing time point would break ORR/DCR/waterfall calculations
    # that assume a complete longitudinal series per subject.
    assessments_per_subject = tumor_assessments_df.groupby("subject_id")[
        "assessment_id"
    ].count()
    expected_subjects = set(randomization_df["subject_id"])
    assert set(assessments_per_subject.index) == expected_subjects, (
        "Every randomized subject must have tumor assessments."
    )
    assert (assessments_per_subject == len(TUMOR_ASSESSMENT_VISIT_NAMES)).all(), (
        "Every randomized subject must have exactly three tumor assessments."
    )

    # Tumor sizes can never be negative -- a measurement below zero has
    # no physical meaning.
    assert (tumor_assessments_df["tumor_size_mm"] >= 0).all(), (
        "Negative tumor size detected."
    )

    # Baseline assessments must always report 0% change from baseline,
    # since a measurement cannot differ from itself.
    baseline_rows = tumor_assessments_df.merge(
        visits_df[["visit_id", "visit_name"]], on="visit_id", how="left"
    )
    baseline_changes = baseline_rows.loc[
        baseline_rows["visit_name"] == "Baseline", "percent_change_from_baseline"
    ]
    assert (baseline_changes == 0.0).all(), "Baseline assessments must have 0% change."

    # Every response category must match what calculate_response_category
    # would independently derive from the stored measurement, guarding
    # against drift between the stored value and the classification rule.
    recalculated = tumor_assessments_df.apply(
        lambda row: calculate_response_category(
            row["tumor_size_mm"], row["percent_change_from_baseline"]
        ),
        axis=1,
    )
    assert (recalculated == tumor_assessments_df["response_category"]).all(), (
        "Response category does not match the calculated percent change."
    )

    # An assessment must always be dated on the same day as the visit it
    # was performed at -- imaging cannot occur outside its own visit.
    visit_date_map = dict(zip(visits_df["visit_id"], visits_df["visit_date"]))
    mismatched_dates = tumor_assessments_df[
        tumor_assessments_df["visit_id"].map(visit_date_map)
        != tumor_assessments_df["assessment_date"]
    ]
    assert mismatched_dates.empty, "Assessment date does not match visit_date."


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def save_csv(df: pd.DataFrame, filename: str, output_dir: Path) -> None:
    """Save a DataFrame to CSV in the specified output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename
    df.to_csv(file_path, index=False)
    print(f"Saved {len(df):>6} rows -> {file_path}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    print("Script Started")

    random.seed(RANDOM_SEED)

    randomization_df, visits_df = load_data(INPUT_DIR)
    tumor_assessments_df = generate_tumor_assessments(randomization_df, visits_df)

    validate_tumor_assessments(randomization_df, visits_df, tumor_assessments_df)

    save_csv(tumor_assessments_df, "tumor_assessments.csv", OUTPUT_DIR)

    print("Tumor assessment generation completed.")


if __name__ == "__main__":
    main()