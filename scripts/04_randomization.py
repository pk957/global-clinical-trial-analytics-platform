"""
04_randomization.py

Assigns every enrolled subject to a treatment arm using permuted block
randomization for the Global Clinical Trial Analytics Platform (Study
CRC-GLB-301). Reads subjects.csv from data/raw/ and writes
randomization.csv.

This script simulates the output of a Clinical Trial Interactive Response
Technology (IRT) system: it is an ETL transformation, not a synthetic
data generator. Subject IDs and study IDs are copied verbatim from
subjects.csv and never regenerated.

Input
-----
data/raw/subjects.csv

Output
------
data/raw/randomization.csv

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

# A block size of 4 with a 1:1 allocation ratio keeps the two treatment
# arms balanced after every complete block, which is the whole point of
# block randomization in a trial: it prevents long, biased runs of a
# single arm while still keeping assignment unpredictable within a block.
BLOCK_SIZE = 4

TREATMENT_ARMS = [
    "NVC-CRC101",
    "Standard of Care + Placebo",
]

RANDOMIZATION_STATUS = "Randomized"

RANDOMIZATION_LAG_MIN_DAYS = 0
RANDOMIZATION_LAG_MAX_DAYS = 2


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> pd.DataFrame:
    """Load the enrolled subjects dataset from the raw data directory."""
    subjects_df = pd.read_csv(input_dir / "subjects.csv")
    return subjects_df


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def random_randomization_date(enrollment_date: date) -> date:
    """Return a random randomization date 0-2 days after enrollment.

    IRT systems typically randomize a subject at or shortly after the
    enrollment visit, so the assigned date can never precede enrollment.
    """
    lag_days = random.randint(RANDOMIZATION_LAG_MIN_DAYS, RANDOMIZATION_LAG_MAX_DAYS)
    return enrollment_date + timedelta(days=lag_days)


# --------------------------------------------------------------------------
# Randomization generation
# --------------------------------------------------------------------------

def generate_block_assignments(num_subjects: int) -> list[str]:
    """Generate a full list of treatment arm assignments using block
    randomization.

    Each complete block of BLOCK_SIZE contains an equal number of
    subjects per arm (2 NVC-CRC101 / 2 Standard of Care + Placebo),
    then the block contents are shuffled so the actual assignment order
    is unpredictable to sites and investigators — this unpredictability
    is the core integrity guarantee of an IRT randomization system.

    If the final block is incomplete (fewer than BLOCK_SIZE subjects
    remain), the remaining subjects are assigned as evenly as possible
    across the two arms and then shuffled.
    """
    per_arm_per_block = BLOCK_SIZE // len(TREATMENT_ARMS)
    full_blocks, remainder = divmod(num_subjects, BLOCK_SIZE)

    assignments: list[str] = []

    # Complete blocks: guarantee a balanced arm count within each block.
    for _ in range(full_blocks):
        block = TREATMENT_ARMS * per_arm_per_block
        random.shuffle(block)
        assignments.extend(block)

    # Final, incomplete block: distribute remaining subjects as evenly
    # as possible across arms rather than leaving the block unbalanced.
    if remainder > 0:
        tail_block = [TREATMENT_ARMS[i % len(TREATMENT_ARMS)] for i in range(remainder)]
        random.shuffle(tail_block)
        assignments.extend(tail_block)

    return assignments


def generate_randomization(subjects_df: pd.DataFrame) -> pd.DataFrame:
    """Derive randomization records for every enrolled subject."""

    # A single batch timestamp reflects that this represents one
    # randomization run/export from the IRT system, not per-row events.
    created_at = datetime.now().isoformat()

    total = len(subjects_df)
    treatment_assignments = generate_block_assignments(total)

    rows = []
    for i, subject_row in subjects_df.iterrows():
        subject_number = i + 1

        enrollment_date = datetime.strptime(
            subject_row["enrollment_date"], "%Y-%m-%d"
        ).date()
        randomization_date = random_randomization_date(enrollment_date)

        rows.append(
            {
                "randomization_id": f"RAND-{subject_number:06d}",
                "subject_id": subject_row["subject_id"],
                "study_id": subject_row["study_id"],
                "treatment_arm": treatment_assignments[i],
                "randomization_date": randomization_date.isoformat(),
                "randomization_status": RANDOMIZATION_STATUS,
                "created_at": created_at,
            }
        )

        if subject_number % 2000 == 0:
            print(f"Randomized {subject_number:>5} / {total} subjects...")

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

    subjects_df = load_data(INPUT_DIR)
    randomization_df = generate_randomization(subjects_df)

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    # Each subject must be randomized exactly once, mirroring the
    # real-world rule that an IRT system never double-randomizes a
    # participant.
    assert randomization_df["subject_id"].is_unique, "Duplicate subject_id detected."

    # Every enrolled subject must have a corresponding randomization
    # record; nobody should be silently dropped by the transformation.
    assert set(subjects_df["subject_id"]) == set(randomization_df["subject_id"]), (
        "Not every enrolled subject was randomized."
    )

    # Randomization can never precede enrollment, since a subject cannot
    # be assigned treatment before agreeing to participate.
    enrollment_date_map = dict(
        zip(subjects_df["subject_id"], subjects_df["enrollment_date"])
    )
    randomization_dates = pd.to_datetime(randomization_df["randomization_date"])
    linked_enrollment_dates = pd.to_datetime(
        randomization_df["subject_id"].map(enrollment_date_map)
    )
    assert (randomization_dates >= linked_enrollment_dates).all(), (
        "Randomization date must occur on or after the enrollment date."
    )

    # Block randomization should keep the two arms close to a 1:1 split;
    # a large imbalance would indicate a bug in the block logic above.
    arm_counts = randomization_df["treatment_arm"].value_counts()
    max_imbalance = abs(arm_counts.iloc[0] - arm_counts.iloc[-1])
    assert max_imbalance <= BLOCK_SIZE, "Treatment allocation is not balanced."

    save_csv(randomization_df, "randomization.csv", OUTPUT_DIR)

    print("Randomization generation completed.")


if __name__ == "__main__":
    main()