"""
09_adverse_events.py

Generates adverse event (AE) records for randomized subjects in the
Global Clinical Trial Analytics Platform (Study CRC-GLB-301). Reads
randomization.csv and visits.csv from data/raw/ and writes
adverse_events.csv.

This script enriches existing subjects with safety data; it never
creates new subjects or visits. Only a realistic subset of subjects
experience adverse events, and each event is anchored to a real
post-baseline visit so onset dates remain fully traceable to the
subject's actual visit schedule.

Input
-----
data/raw/randomization.csv
data/raw/visits.csv

Output
------
data/raw/adverse_events.csv

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

# Not every subject on an oncology trial experiences a reportable AE;
# modeling only a realistic fraction of subjects keeps the dataset
# consistent with real-world safety reporting rates rather than
# implying universal toxicity.
AE_SUBJECT_FRACTION_MIN = 0.40
AE_SUBJECT_FRACTION_MAX = 0.50

AE_EVENTS_PER_SUBJECT_MIN = 1
AE_EVENTS_PER_SUBJECT_MAX = 4

# Baseline is an assessment/screening-style visit, not a treatment
# visit -- a subject cannot have a treatment-emergent AE before they
# have received any study drug, so AEs are only anchored to visits
# after Baseline (visit_number > 1).
BASELINE_VISIT_NUMBER = 1

# The preferred terms below represent the standard toxicity profile
# expected for an oncology chemotherapy regimen (GI, hematologic,
# hepatic, and neurologic events), rather than an arbitrary term list.
AE_TERMS = [
    "Headache",
    "Nausea",
    "Vomiting",
    "Diarrhea",
    "Fatigue",
    "Anemia",
    "Neutropenia",
    "Constipation",
    "Peripheral Neuropathy",
    "Elevated Liver Enzymes",
    "Abdominal Pain",
    "Fever",
]

# Severity follows a typical oncology safety profile: most events are
# low-grade and manageable, with progressively fewer higher-grade
# events, mirroring real CTCAE grade distributions.
SEVERITY_LEVELS = ["Mild", "Moderate", "Severe"]
SEVERITY_WEIGHTS = [0.55, 0.35, 0.10]

# Only a small minority of AEs meet regulatory seriousness criteria
# (e.g. hospitalization, life-threatening) -- most reported events are
# expected, non-serious toxicities.
SERIOUS_EVENT_VALUES = ["Yes", "No"]
SERIOUS_EVENT_WEIGHTS = [0.05, 0.95]

# Causality assessment is investigator-driven and skews toward "related"
# categories on an active oncology study, since most collected AEs are
# at least possibly attributable to the study drug or regimen.
RELATIONSHIP_VALUES = [
    "Definitely Related",
    "Probably Related",
    "Possibly Related",
    "Unrelated",
]
RELATIONSHIP_WEIGHTS = [0.20, 0.35, 0.25, 0.20]

# Outcome distribution reflects that most oncology AEs resolve with
# supportive care, a smaller share are ongoing at data cut, and only a
# rare few are fatal -- consistent with typical trial safety profiles.
OUTCOME_RECOVERED = "Recovered"
OUTCOME_RECOVERING = "Recovering"
OUTCOME_NOT_RECOVERED = "Not Recovered"
OUTCOME_FATAL = "Fatal"

OUTCOME_VALUES = [
    OUTCOME_RECOVERED,
    OUTCOME_RECOVERING,
    OUTCOME_NOT_RECOVERED,
    OUTCOME_FATAL,
]
OUTCOME_WEIGHTS = [0.70, 0.20, 0.09, 0.01]

RESOLUTION_LAG_MIN_DAYS = 1
RESOLUTION_LAG_MAX_DAYS = 30

PROGRESS_INTERVAL = 5000


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the randomization and visits datasets from the raw data directory."""
    randomization_df = pd.read_csv(input_dir / "randomization.csv")
    visits_df = pd.read_csv(input_dir / "visits.csv")
    return randomization_df, visits_df


# --------------------------------------------------------------------------
# Adverse event generation
# --------------------------------------------------------------------------

def select_subjects_with_events(subject_ids: list[str]) -> set[str]:
    """Select the subset of subjects who will report at least one AE.

    The fraction is drawn from a range (rather than a single fixed
    percentage) so the resulting AE incidence rate varies slightly run
    to run in a realistic way while still landing in the expected
    40-50% band requested by the safety reporting requirements.
    """
    fraction = random.uniform(AE_SUBJECT_FRACTION_MIN, AE_SUBJECT_FRACTION_MAX)
    sample_size = round(len(subject_ids) * fraction)
    return set(random.sample(subject_ids, sample_size))


def _build_post_baseline_visit_map(visits_df: pd.DataFrame) -> dict[str, list[pd.Series]]:
    """Build subject_id -> list of post-baseline visit rows.

    AEs are only ever anchored to a visit after Baseline (see
    BASELINE_VISIT_NUMBER above), so this lookup is pre-filtered once
    rather than re-filtering visits.csv for every generated event.
    """
    post_baseline_visits = visits_df[visits_df["visit_number"] > BASELINE_VISIT_NUMBER]

    visit_map: dict[str, list[pd.Series]] = {}
    for subject_id, group in post_baseline_visits.groupby("subject_id"):
        visit_map[subject_id] = [row for _, row in group.iterrows()]

    return visit_map


def _generate_single_event(
    ae_number: int, visit_row: pd.Series
) -> dict[str, object]:
    """Generate one adverse event record anchored to a specific visit.

    Severity, relationship, and outcome are sampled independently per
    the protocol-informed weights above, but outcome and serious_event
    are then reconciled together (see below) because a Fatal outcome
    is, by regulatory definition, always a serious event.
    """
    onset_date = datetime.strptime(visit_row["visit_date"], "%Y-%m-%d").date()

    severity = random.choices(SEVERITY_LEVELS, weights=SEVERITY_WEIGHTS, k=1)[0]
    relationship_to_drug = random.choices(
        RELATIONSHIP_VALUES, weights=RELATIONSHIP_WEIGHTS, k=1
    )[0]
    outcome = random.choices(OUTCOME_VALUES, weights=OUTCOME_WEIGHTS, k=1)[0]

    # A Fatal outcome is always regulatorily "serious" by definition, so
    # it overrides the independently sampled seriousness flag rather
    # than risking a contradictory Fatal/non-serious combination.
    if outcome == OUTCOME_FATAL:
        serious_event = "Yes"
    else:
        serious_event = random.choices(
            SERIOUS_EVENT_VALUES, weights=SERIOUS_EVENT_WEIGHTS, k=1
        )[0]

    # Resolution date depends entirely on the outcome: only a Recovered
    # or Fatal event has a defined resolution date, while an ongoing
    # (Recovering/Not Recovered) event is, by definition, not yet
    # resolved and therefore has no resolution date.
    if outcome == OUTCOME_RECOVERED:
        lag_days = random.randint(RESOLUTION_LAG_MIN_DAYS, RESOLUTION_LAG_MAX_DAYS)
        resolution_date = onset_date + timedelta(days=lag_days)
    elif outcome == OUTCOME_FATAL:
        resolution_date = onset_date
    else:
        resolution_date = None

    return {
        "visit_id": visit_row["visit_id"],
        "randomization_id": visit_row["randomization_id"],
        "subject_id": visit_row["subject_id"],
        "study_id": visit_row["study_id"],
        "ae_term": random.choice(AE_TERMS),
        "severity": severity,
        "serious_event": serious_event,
        "relationship_to_drug": relationship_to_drug,
        "onset_date": onset_date.isoformat(),
        "resolution_date": resolution_date.isoformat() if resolution_date else None,
        "outcome": outcome,
        "created_at": None,  # populated in bulk by the caller
    }


def generate_adverse_events(
    randomization_df: pd.DataFrame, visits_df: pd.DataFrame
) -> pd.DataFrame:
    """Generate AE records for a realistic subset of randomized subjects."""

    # A single batch timestamp reflects that this represents one safety
    # data extract/export, not per-row collection events.
    created_at = datetime.now().isoformat()

    subject_ids = randomization_df["subject_id"].tolist()
    subjects_with_events = select_subjects_with_events(subject_ids)
    post_baseline_visit_map = _build_post_baseline_visit_map(visits_df)

    rows: list[dict[str, object]] = []
    ae_counter = 0

    for subject_id in subjects_with_events:
        subject_visits = post_baseline_visit_map.get(subject_id)
        if not subject_visits:
            # A subject with no post-baseline visit (e.g. an early
            # withdrawal edge case) simply cannot have an anchored AE.
            continue

        num_events = random.randint(
            AE_EVENTS_PER_SUBJECT_MIN, AE_EVENTS_PER_SUBJECT_MAX
        )

        for _ in range(num_events):
            ae_counter += 1
            visit_row = random.choice(subject_visits)

            event = _generate_single_event(ae_counter, visit_row)
            event["ae_id"] = f"AE-{ae_counter:06d}"
            event["created_at"] = created_at
            rows.append(event)

            if ae_counter % PROGRESS_INTERVAL == 0:
                print(f"Generated {ae_counter:>6} adverse events...")

    # Reorder columns to match the required output schema exactly.
    columns = [
        "ae_id",
        "visit_id",
        "randomization_id",
        "subject_id",
        "study_id",
        "ae_term",
        "severity",
        "serious_event",
        "relationship_to_drug",
        "onset_date",
        "resolution_date",
        "outcome",
        "created_at",
    ]
    return pd.DataFrame(rows, columns=columns)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_adverse_events(
    randomization_df: pd.DataFrame,
    visits_df: pd.DataFrame,
    adverse_events_df: pd.DataFrame,
) -> None:
    """Run referential integrity and business-rule checks on the output.

    Every check below raises a specific, descriptive exception so that
    a pipeline failure immediately points to the exact business rule
    that was violated rather than a generic assertion.
    """
    if not adverse_events_df["ae_id"].is_unique:
        raise ValueError("Duplicate ae_id detected in adverse_events.csv.")

    valid_visit_ids = set(visits_df["visit_id"])
    if not set(adverse_events_df["visit_id"]).issubset(valid_visit_ids):
        raise ValueError("One or more visit_id values do not exist in visits.csv.")

    valid_subject_ids = set(randomization_df["subject_id"])
    if not set(adverse_events_df["subject_id"]).issubset(valid_subject_ids):
        raise ValueError("One or more subject_id values do not exist in randomization.csv.")

    valid_randomization_ids = set(randomization_df["randomization_id"])
    if not set(adverse_events_df["randomization_id"]).issubset(valid_randomization_ids):
        raise ValueError(
            "One or more randomization_id values do not exist in randomization.csv."
        )

    if not set(adverse_events_df["severity"]).issubset(set(SEVERITY_LEVELS)):
        raise ValueError("Invalid severity value detected.")

    if not set(adverse_events_df["serious_event"]).issubset(set(SERIOUS_EVENT_VALUES)):
        raise ValueError("Invalid serious_event value detected.")

    if not set(adverse_events_df["outcome"]).issubset(set(OUTCOME_VALUES)):
        raise ValueError("Invalid outcome value detected.")

    # A Fatal outcome must always be flagged as a serious event -- this
    # is a regulatory requirement, not just a modeling convenience.
    fatal_events = adverse_events_df[adverse_events_df["outcome"] == OUTCOME_FATAL]
    if not (fatal_events["serious_event"] == "Yes").all():
        raise ValueError("Every Fatal outcome must have serious_event = Yes.")

    # Recovering and Not Recovered events are, by definition, ongoing
    # and therefore must not carry a resolution date.
    ongoing_events = adverse_events_df[
        adverse_events_df["outcome"].isin([OUTCOME_RECOVERING, OUTCOME_NOT_RECOVERED])
    ]
    if ongoing_events["resolution_date"].notna().any():
        raise ValueError(
            "Recovering and Not Recovered events must have a blank resolution_date."
        )

    # A Fatal event's resolution date must equal its onset date, since
    # death is recorded as occurring on the day of the event itself.
    if not (fatal_events["resolution_date"] == fatal_events["onset_date"]).all():
        raise ValueError("Fatal events must have resolution_date equal to onset_date.")

    # Resolution date, when present, can never precede onset date --
    # an event cannot resolve before it began.
    dated_events = adverse_events_df[adverse_events_df["resolution_date"].notna()]
    onset_dates = pd.to_datetime(dated_events["onset_date"])
    resolution_dates = pd.to_datetime(dated_events["resolution_date"])
    if not (resolution_dates >= onset_dates).all():
        raise ValueError("resolution_date must never occur before onset_date.")


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
    adverse_events_df = generate_adverse_events(randomization_df, visits_df)

    validate_adverse_events(randomization_df, visits_df, adverse_events_df)

    save_csv(adverse_events_df, "adverse_events.csv", OUTPUT_DIR)

    print("Adverse events generation completed.")


if __name__ == "__main__":
    main()