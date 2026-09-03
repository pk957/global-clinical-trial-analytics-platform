"""
10_study_completion.py

Generates the final study completion record for every randomized
subject in the Global Clinical Trial Analytics Platform (Study
CRC-GLB-301). Reads randomization.csv, visits.csv, and
adverse_events.csv from data/raw/ and writes study_completion.csv.

This is the final script in the ETL pipeline: it never creates new
subjects, only closes out each existing one with a single completion
record. A subject's completion outcome must be internally consistent
with their own visit history and safety data -- most importantly, a
subject can only be recorded as having died if a matching Fatal
adverse event actually exists for them.

Input
-----
data/raw/randomization.csv
data/raw/visits.csv
data/raw/adverse_events.csv

Output
------
data/raw/study_completion.csv

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

END_OF_TREATMENT_VISIT_NAME = "End of Treatment"

FATAL_OUTCOME = "Fatal"

STATUS_COMPLETED = "Completed"
STATUS_WITHDRAWN = "Withdrawn"
STATUS_LOST_TO_FOLLOW_UP = "Lost to Follow-up"
STATUS_PROTOCOL_DEVIATION = "Protocol Deviation"
STATUS_DEATH = "Death"

VALID_STUDY_STATUSES = [
    STATUS_COMPLETED,
    STATUS_WITHDRAWN,
    STATUS_LOST_TO_FOLLOW_UP,
    STATUS_PROTOCOL_DEVIATION,
    STATUS_DEATH,
]

# The suggested overall distribution below reflects a well-run,
# well-retained Phase III oncology study: most subjects finish per
# protocol, a modest share withdraw or are lost, and only a small
# minority experience a protocol deviation or death. Death is handled
# separately from this weighted draw (see generate_study_completion)
# because it must be *earned* by an actual Fatal AE, not assigned by
# chance alongside the other statuses.
NON_DEATH_STATUS_WEIGHTS = {
    STATUS_COMPLETED: 0.82,
    STATUS_WITHDRAWN: 0.08,
    STATUS_LOST_TO_FOLLOW_UP: 0.05,
    STATUS_PROTOCOL_DEVIATION: 0.03,
}

PRIMARY_REASON_COMPLETED = "Completed per Protocol"
PRIMARY_REASON_LOST_TO_FOLLOW_UP = "Lost Contact"
PRIMARY_REASON_PROTOCOL_DEVIATION = "Major Protocol Deviation"
PRIMARY_REASON_DEATH = "Death"

# A withdrawal can be driven by several distinct causes; sampling among
# them (rather than using a single fixed reason) reflects that
# "Withdrawn" is a status category, not a single cause, in real trial
# disposition data.
WITHDRAWAL_REASONS = [
    "Subject Decision",
    "Adverse Event",
    "Investigator Decision",
]

PROGRESS_INTERVAL = 5000


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load randomization, visits, and adverse events datasets."""
    randomization_df = pd.read_csv(input_dir / "randomization.csv")
    visits_df = pd.read_csv(input_dir / "visits.csv")
    adverse_events_df = pd.read_csv(input_dir / "adverse_events.csv")
    return randomization_df, visits_df, adverse_events_df


# --------------------------------------------------------------------------
# Study completion generation
# --------------------------------------------------------------------------

def _build_end_of_treatment_date_map(visits_df: pd.DataFrame) -> dict[str, str]:
    """Build subject_id -> End of Treatment visit_date.

    Completion date for every non-death subject is anchored to their
    actual End of Treatment visit rather than an independently
    generated date, guaranteeing that the completion record stays
    consistent with the subject's real visit history.
    """
    eot_visits = visits_df[visits_df["visit_name"] == END_OF_TREATMENT_VISIT_NAME]
    return dict(zip(eot_visits["subject_id"], eot_visits["visit_date"]))


def _build_fatal_ae_date_map(adverse_events_df: pd.DataFrame) -> dict[str, str]:
    """Build subject_id -> onset_date for subjects with a Fatal AE.

    Death is not a status that can be assigned at will: it must be
    backed by an actual Fatal adverse event record. This lookup is
    what enforces that dependency, and it also supplies the completion
    date for Death subjects, since a subject's disposition date must
    equal the date they actually died, not their (never-reached)
    End of Treatment visit.
    """
    fatal_events = adverse_events_df[adverse_events_df["outcome"] == FATAL_OUTCOME]
    # A subject could theoretically have more than one Fatal AE record;
    # the earliest onset date is used as the date of death.
    fatal_events_sorted = fatal_events.sort_values("onset_date")
    return dict(
        zip(fatal_events_sorted["subject_id"], fatal_events_sorted["onset_date"])
    )


def _assign_non_death_status() -> str:
    """Randomly draw a disposition status for a subject who did not die.

    Weights are renormalized over the four non-death categories so
    that, combined with the separately-derived Death subjects, the
    overall study population lands close to the suggested 82/8/5/3/2
    distribution without ever assigning Death by chance.
    """
    statuses = list(NON_DEATH_STATUS_WEIGHTS.keys())
    weights = list(NON_DEATH_STATUS_WEIGHTS.values())
    return random.choices(statuses, weights=weights, k=1)[0]


def _primary_reason_for_status(study_status: str) -> str:
    """Map a study status to its corresponding primary reason.

    Completed, Lost to Follow-up, Protocol Deviation, and Death each
    have a single canonical reason by protocol convention; only
    Withdrawn has multiple plausible underlying causes.
    """
    if study_status == STATUS_COMPLETED:
        return PRIMARY_REASON_COMPLETED
    if study_status == STATUS_WITHDRAWN:
        return random.choice(WITHDRAWAL_REASONS)
    if study_status == STATUS_LOST_TO_FOLLOW_UP:
        return PRIMARY_REASON_LOST_TO_FOLLOW_UP
    if study_status == STATUS_PROTOCOL_DEVIATION:
        return PRIMARY_REASON_PROTOCOL_DEVIATION
    if study_status == STATUS_DEATH:
        return PRIMARY_REASON_DEATH
    raise ValueError(f"Unrecognized study_status: {study_status}")


def generate_study_completion(
    randomization_df: pd.DataFrame,
    visits_df: pd.DataFrame,
    adverse_events_df: pd.DataFrame,
) -> pd.DataFrame:
    """Generate exactly one study completion record per randomized subject."""

    # A single batch timestamp reflects that this represents one study
    # disposition export, not per-row events.
    created_at = datetime.now().isoformat()

    eot_date_map = _build_end_of_treatment_date_map(visits_df)
    fatal_ae_date_map = _build_fatal_ae_date_map(adverse_events_df)

    total_subjects = len(randomization_df)
    completion_counter = 0

    rows = []
    for _, randomization_row in randomization_df.iterrows():
        completion_counter += 1
        subject_id = randomization_row["subject_id"]

        # A subject can only be recorded as Death if they actually have
        # a Fatal AE on file -- this is the core referential rule the
        # entire script exists to enforce.
        if subject_id in fatal_ae_date_map:
            study_status = STATUS_DEATH
            completion_date = fatal_ae_date_map[subject_id]
        else:
            study_status = _assign_non_death_status()
            completion_date = eot_date_map.get(subject_id)

        primary_reason = _primary_reason_for_status(study_status)

        rows.append(
            {
                "completion_id": f"CMP-{completion_counter:06d}",
                "randomization_id": randomization_row["randomization_id"],
                "subject_id": subject_id,
                "study_id": randomization_row["study_id"],
                "study_status": study_status,
                "primary_reason": primary_reason,
                "completion_date": completion_date,
                "created_at": created_at,
            }
        )

        if completion_counter % PROGRESS_INTERVAL == 0:
            print(
                f"Generated {completion_counter:>6} / {total_subjects} "
                "study completion records..."
            )

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_study_completion(
    randomization_df: pd.DataFrame,
    visits_df: pd.DataFrame,
    adverse_events_df: pd.DataFrame,
    study_completion_df: pd.DataFrame,
) -> None:
    """Run referential integrity and business-rule checks on the output.

    Every check below raises a specific, descriptive exception so that
    a pipeline failure immediately points to the exact business rule
    that was violated rather than a generic assertion.
    """
    if not study_completion_df["completion_id"].is_unique:
        raise ValueError("Duplicate completion_id detected in study_completion.csv.")

    if study_completion_df["subject_id"].duplicated().any():
        raise ValueError("Duplicate subject_id detected in study_completion.csv.")

    # Every randomized subject must appear exactly once -- the study
    # disposition table must be a complete, one-to-one closeout of the
    # randomized population.
    expected_subjects = set(randomization_df["subject_id"])
    actual_subjects = set(study_completion_df["subject_id"])
    if actual_subjects != expected_subjects:
        raise ValueError("Every randomized subject must appear exactly once.")

    if study_completion_df["completion_date"].isna().any():
        raise ValueError("completion_date must not be null for any subject.")

    if not set(study_completion_df["study_status"]).issubset(set(VALID_STUDY_STATUSES)):
        raise ValueError("Invalid study_status value detected.")

    valid_reasons = {
        PRIMARY_REASON_COMPLETED,
        PRIMARY_REASON_LOST_TO_FOLLOW_UP,
        PRIMARY_REASON_PROTOCOL_DEVIATION,
        PRIMARY_REASON_DEATH,
        *WITHDRAWAL_REASONS,
    }
    if not set(study_completion_df["primary_reason"]).issubset(valid_reasons):
        raise ValueError("Invalid primary_reason value detected.")

    # A Death status must always be backed by a real Fatal AE record --
    # without this, the completion table would imply a death that has
    # no corresponding safety documentation.
    fatal_ae_date_map = _build_fatal_ae_date_map(adverse_events_df)
    death_rows = study_completion_df[study_completion_df["study_status"] == STATUS_DEATH]
    if not set(death_rows["subject_id"]).issubset(set(fatal_ae_date_map.keys())):
        raise ValueError("Death status requires a matching Fatal adverse event.")

    # For Death subjects, the completion date must equal the date of
    # their Fatal AE -- the disposition date must reflect when the
    # subject actually died, not an arbitrary later date.
    death_dates_match = death_rows["subject_id"].map(fatal_ae_date_map) == death_rows[
        "completion_date"
    ]
    if not death_dates_match.all():
        raise ValueError("Death completion_date must equal the Fatal AE onset_date.")

    # For every non-death subject, completion_date must equal their own
    # End of Treatment visit date -- a subject's disposition cannot be
    # dated independently of when they actually finished treatment.
    eot_date_map = _build_end_of_treatment_date_map(visits_df)
    non_death_rows = study_completion_df[
        study_completion_df["study_status"] != STATUS_DEATH
    ]
    eot_dates_match = non_death_rows["subject_id"].map(eot_date_map) == non_death_rows[
        "completion_date"
    ]
    if not eot_dates_match.all():
        raise ValueError(
            "completion_date must equal the End of Treatment visit date "
            "for all non-death subjects."
        )


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

    randomization_df, visits_df, adverse_events_df = load_data(INPUT_DIR)
    study_completion_df = generate_study_completion(
        randomization_df, visits_df, adverse_events_df
    )

    validate_study_completion(
        randomization_df, visits_df, adverse_events_df, study_completion_df
    )

    save_csv(study_completion_df, "study_completion.csv", OUTPUT_DIR)

    print("Study completion generation completed.")


if __name__ == "__main__":
    main()