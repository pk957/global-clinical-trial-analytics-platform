"""
05_visits.py

Generates the scheduled protocol visits for every randomized subject in
the Global Clinical Trial Analytics Platform (Study CRC-GLB-301). Reads
randomization.csv from data/raw/ and writes visits.csv.

This script simulates the visit schedule produced by an Electronic Data
Capture (EDC) system: it is an ETL transformation, not a synthetic data
generator. Every randomized subject receives exactly six protocol
visits, each dated relative to that subject's randomization_date.

Input
-----
data/raw/randomization.csv

Output
------
data/raw/visits.csv

Author: Senior Data Engineering Team
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------
# Configuration / Constants
# --------------------------------------------------------------------------

RANDOM_SEED = 42

INPUT_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/raw")

# The visit schedule is fixed by the study protocol, not randomized: every
# subject follows the same cadence of assessments so that efficacy and
# safety data are comparable across the whole trial population. Each
# tuple is (visit_number, visit_name, day_offset_from_randomization).
VISIT_SCHEDULE = [
    (1, "Baseline", 0),
    (2, "Cycle 1 Day 1", 1),
    (3, "Cycle 2 Day 1", 22),
    (4, "Cycle 3 Day 1", 43),
    (5, "End of Treatment", 85),
    (6, "Safety Follow-up", 115),
]

VISIT_STATUS = "Completed"

PROGRESS_INTERVAL = 5000


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> pd.DataFrame:
    """Load the randomized subjects dataset from the raw data directory."""
    randomization_df = pd.read_csv(input_dir / "randomization.csv")
    return randomization_df


# --------------------------------------------------------------------------
# Visit generation
# --------------------------------------------------------------------------

def generate_visits(randomization_df: pd.DataFrame) -> pd.DataFrame:
    """Expand each randomized subject into their full set of protocol visits.

    Every subject must complete the same six visits so that per-visit
    endpoints (labs, tumor assessments, adverse events, etc. in the
    downstream scripts) can be joined back to a consistent visit
    structure across the entire study population.
    """

    # A single batch timestamp reflects that this represents one visit
    # scheduling run/export from the EDC system, not per-row events.
    created_at = datetime.now().isoformat()

    total_visits = len(randomization_df) * len(VISIT_SCHEDULE)
    total_subjects = len(randomization_df)

    rows = []
    visit_counter = 0

    for _, randomization_row in randomization_df.iterrows():
        randomization_date = datetime.strptime(
            randomization_row["randomization_date"], "%Y-%m-%d"
        ).date()

        # Every visit date is anchored to randomization_date rather than
        # to the previous visit, matching how protocol day offsets are
        # defined in the study schedule of assessments.
        for visit_number, visit_name, day_offset in VISIT_SCHEDULE:
            visit_counter += 1
            visit_date = randomization_date + timedelta(days=day_offset)

            rows.append(
                {
                    "visit_id": f"VIS-{visit_counter:06d}",
                    "randomization_id": randomization_row["randomization_id"],
                    "subject_id": randomization_row["subject_id"],
                    "study_id": randomization_row["study_id"],
                    "visit_number": visit_number,
                    "visit_name": visit_name,
                    "visit_date": visit_date.isoformat(),
                    "visit_status": VISIT_STATUS,
                    "created_at": created_at,
                }
            )

            if visit_counter % PROGRESS_INTERVAL == 0:
                print(f"Generated {visit_counter:>6} / {total_visits} visits...")

    print(f"Scheduled {len(VISIT_SCHEDULE)} visits for {total_subjects} subjects.")

    return pd.DataFrame(rows)


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
# Main orchestration
# --------------------------------------------------------------------------

def main() -> None:
    print("Script Started")

    random.seed(RANDOM_SEED)

    randomization_df = load_data(INPUT_DIR)
    visits_df = generate_visits(randomization_df)

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    # visit_id must be globally unique so downstream scripts can safely
    # use it as a join key without collisions.
    assert visits_df["visit_id"].is_unique, "Duplicate visit_id detected."

    # Every randomized subject must receive exactly six visits; a
    # missing or extra visit would corrupt the schedule-of-assessments
    # structure that downstream scripts (labs, AEs, tumor assessments,
    # dispensing) depend on.
    visits_per_subject = visits_df.groupby("subject_id")["visit_id"].count()
    assert (visits_per_subject == len(VISIT_SCHEDULE)).all(), (
        "Every randomized subject must have exactly six visits."
    )

    # Visit numbers must be sequential (1-6) for every subject, matching
    # the fixed protocol schedule rather than an arbitrary ordering.
    expected_numbers = {number for number, _, _ in VISIT_SCHEDULE}
    numbers_per_subject = visits_df.groupby("subject_id")["visit_number"].apply(set)
    assert (numbers_per_subject == expected_numbers).all(), (
        "Visit numbers are not sequential for every subject."
    )

    # Visit dates must be chronological per subject, since a later
    # protocol visit can never occur before an earlier one.
    sorted_visits = visits_df.sort_values(["subject_id", "visit_number"])
    date_diffs = (
        sorted_visits.groupby("subject_id")["visit_date"]
        .apply(lambda dates: pd.to_datetime(dates).is_monotonic_increasing)
    )
    assert date_diffs.all(), "Visit dates are not chronological for every subject."

    save_csv(visits_df, "visits.csv", OUTPUT_DIR)

    print("Visits generation completed.")


if __name__ == "__main__":
    main()