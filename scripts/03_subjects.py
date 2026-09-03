"""
03_subjects.py

Transforms eligible screening records into enrolled subjects for the
Global Clinical Trial Analytics Platform (Study CRC-GLB-301).

This is a transformation script, not a synthetic data generator: every
subject is derived directly from an "Eligible" row in screening.csv, and
no new participants are invented.

Input
-----
data/raw/screening.csv

Output
------
data/raw/subjects.csv

Author: Senior Data Engineering Team
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------
# Configuration / Constants
# --------------------------------------------------------------------------

RANDOM_SEED = 42

INPUT_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/raw")

ELIGIBLE_STATUS = "Eligible"
SUBJECT_STATUS = "Enrolled"

ENROLLMENT_LAG_MIN_DAYS = 1
ENROLLMENT_LAG_MAX_DAYS = 14


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> pd.DataFrame:
    """Load the screening dataset from the raw data directory."""
    screening_df = pd.read_csv(input_dir / "screening.csv")
    return screening_df


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def random_enrollment_date(screening_date: date) -> date:
    """Return a random enrollment date 1-14 days after the screening date."""
    lag_days = random.randint(ENROLLMENT_LAG_MIN_DAYS, ENROLLMENT_LAG_MAX_DAYS)
    return screening_date + timedelta(days=lag_days)


# --------------------------------------------------------------------------
# Subject generation
# --------------------------------------------------------------------------

def generate_subjects(screening_df: pd.DataFrame) -> pd.DataFrame:
    """Derive enrolled subject records from eligible screening records."""

    # Only participants who passed screening become subjects.
    eligible_df = screening_df[
        screening_df["eligibility_status"] == ELIGIBLE_STATUS
    ].reset_index(drop=True)

    created_at = datetime.now().isoformat()

    rows = []
    total = len(eligible_df)
    for i, screening_row in eligible_df.iterrows():
        subject_number = i + 1

        screening_date = datetime.strptime(
            screening_row["screening_date"], "%Y-%m-%d"
        ).date()
        enrollment_date = random_enrollment_date(screening_date)

        rows.append(
            {
                "subject_id": f"SUB-{subject_number:06d}",
                "screening_id": screening_row["screening_id"],
                "study_id": screening_row["study_id"],
                "site_id": screening_row["site_id"],
                "investigator_id": screening_row["investigator_id"],
                "country_id": screening_row["country_id"],
                "enrollment_date": enrollment_date.isoformat(),
                "age": screening_row["age"],
                "gender": screening_row["gender"],
                "subject_status": SUBJECT_STATUS,
                "created_at": created_at,
            }
        )

        if subject_number % 2000 == 0:
            print(f"Generated {subject_number:>5} / {total} subject records...")

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def save_csv(df: pd.DataFrame, filename: str, output_dir: Path) -> None:
    """Save a DataFrame to CSV in the specified output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename
    df.to_csv(file_path, index=False)
    print(f"Saved {len(df):>5} rows -> {file_path}")


# --------------------------------------------------------------------------
# Main orchestration
# --------------------------------------------------------------------------

def main() -> None:
    print("Script Started")

    random.seed(RANDOM_SEED)

    screening_df = load_data(INPUT_DIR)
    subjects_df = generate_subjects(screening_df)

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    # Every screening_id referenced by a subject must be unique.
    assert subjects_df["screening_id"].is_unique, "Duplicate screening_id detected."

    # Every subject must have originated from an Eligible screening record.
    eligible_screening_ids = set(
        screening_df.loc[
            screening_df["eligibility_status"] == ELIGIBLE_STATUS, "screening_id"
        ]
    )
    assert set(subjects_df["screening_id"]).issubset(eligible_screening_ids), (
        "Subject derived from a non-eligible screening record."
    )

    # Enrollment date must always be strictly after the screening date.
    screening_date_map = dict(
        zip(screening_df["screening_id"], screening_df["screening_date"])
    )
    enrollment_dates = pd.to_datetime(subjects_df["enrollment_date"])
    linked_screening_dates = pd.to_datetime(
        subjects_df["screening_id"].map(screening_date_map)
    )
    assert (enrollment_dates > linked_screening_dates).all(), (
        "Enrollment date must occur after the screening date."
    )

    save_csv(subjects_df, "subjects.csv", OUTPUT_DIR)

    print("Subjects generation completed.")


if __name__ == "__main__":
    main()