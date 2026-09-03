"""
02_screening.py

Generates subject screening data for the Global Clinical Trial Analytics
Platform (Study CRC-GLB-301). Reads master data produced by
01_master_data.py from data/raw/ and writes screening.csv.

Inputs
------
data/raw/studies.csv
data/raw/sites.csv
data/raw/investigators.csv
data/raw/countries.csv

Output
------
data/raw/screening.csv

Author: Senior Data Engineering Team
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Configuration / Constants
# --------------------------------------------------------------------------

RANDOM_SEED = 42

INPUT_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/raw")

NUM_SCREENING_RECORDS = 8000

SCREENING_DATE_START = date(2025, 1, 1)
SCREENING_DATE_END = date(2025, 12, 31)

ELIGIBLE_STATUS = "Eligible"
SCREEN_FAILURE_STATUS = "Screen Failure"
ELIGIBILITY_STATUSES = [ELIGIBLE_STATUS, SCREEN_FAILURE_STATUS]
ELIGIBILITY_WEIGHTS = [0.78, 0.22]

SCREEN_FAILURE_REASONS = [
    "Inclusion Criteria Not Met",
    "Exclusion Criteria Met",
    "Abnormal Laboratory Values",
    "Withdrew Consent",
]

GENDERS = ["Male", "Female"]

AGE_MIN = 18
AGE_MAX = 85

ALPHABET = [chr(c) for c in range(ord("A"), ord("Z") + 1)]


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_data(input_dir: Path) -> dict[str, pd.DataFrame]:
    """Load required master data CSVs from the raw data directory."""
    studies_df = pd.read_csv(input_dir / "studies.csv")
    sites_df = pd.read_csv(input_dir / "sites.csv")
    investigators_df = pd.read_csv(input_dir / "investigators.csv")
    countries_df = pd.read_csv(input_dir / "countries.csv")

    return {
        "studies": studies_df,
        "sites": sites_df,
        "investigators": investigators_df,
        "countries": countries_df,
    }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def random_date(start: date, end: date) -> date:
    """Return a random date between start and end (inclusive)."""
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, delta_days))


def generate_initials() -> str:
    """Generate realistic two-uppercase-letter subject initials."""
    return "".join(random.choices(ALPHABET, k=2))


def build_site_investigator_map(investigators_df: pd.DataFrame) -> dict[str, list[str]]:
    """Build a mapping of site_id -> list of investigator_ids at that site."""
    site_map: dict[str, list[str]] = {}
    for site_id, group in investigators_df.groupby("site_id"):
        site_map[site_id] = group["investigator_id"].tolist()
    return site_map


# --------------------------------------------------------------------------
# Screening generation
# --------------------------------------------------------------------------

def generate_screening(
    studies_df: pd.DataFrame,
    sites_df: pd.DataFrame,
    investigators_df: pd.DataFrame,
    num_records: int,
) -> pd.DataFrame:
    """Generate the screening dataset with valid foreign key relationships."""

    # There is only one study for this project.
    study_id = studies_df.loc[0, "study_id"]

    # Pre-compute lookups to keep the generation loop fast and simple.
    site_ids = sites_df["site_id"].tolist()
    site_country_map = dict(zip(sites_df["site_id"], sites_df["country_id"]))
    site_investigator_map = build_site_investigator_map(investigators_df)

    created_at = datetime.now().isoformat()

    rows = []
    for i in range(1, num_records + 1):
        # Randomly assign a site, then derive country and investigator
        # from that site to guarantee referential integrity.
        site_id = random.choice(site_ids)
        country_id = site_country_map[site_id]
        investigator_id = random.choice(site_investigator_map[site_id])

        # Determine eligibility using the configured 78/22 split.
        eligibility_status = np.random.choice(
            ELIGIBILITY_STATUSES, p=ELIGIBILITY_WEIGHTS
        )

        if eligibility_status == SCREEN_FAILURE_STATUS:
            screen_failure_reason = random.choice(SCREEN_FAILURE_REASONS)
        else:
            screen_failure_reason = None

        screening_date = random_date(SCREENING_DATE_START, SCREENING_DATE_END)

        rows.append(
            {
                "screening_id": f"SCR-{i:06d}",
                "study_id": study_id,
                "site_id": site_id,
                "investigator_id": investigator_id,
                "country_id": country_id,
                "screening_date": screening_date.isoformat(),
                "subject_initials": generate_initials(),
                "age": random.randint(AGE_MIN, AGE_MAX),
                "gender": random.choice(GENDERS),
                "eligibility_status": eligibility_status,
                "screen_failure_reason": screen_failure_reason,
                "informed_consent": "Yes",
                "created_at": created_at,
            }
        )

        if i % 2000 == 0:
            print(f"Generated {i:>5} / {num_records} screening records...")

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
    np.random.seed(RANDOM_SEED)

    data = load_data(INPUT_DIR)

    screening_df = generate_screening(
        studies_df=data["studies"],
        sites_df=data["sites"],
        investigators_df=data["investigators"],
        num_records=NUM_SCREENING_RECORDS,
    )

    # ----------------------------------------------------------------
    # Referential integrity checks
    # ----------------------------------------------------------------
    assert set(screening_df["study_id"]).issubset(set(data["studies"]["study_id"]))
    assert set(screening_df["site_id"]).issubset(set(data["sites"]["site_id"]))
    assert set(screening_df["investigator_id"]).issubset(
        set(data["investigators"]["investigator_id"])
    )
    assert set(screening_df["country_id"]).issubset(set(data["countries"]["country_id"]))
    assert len(screening_df) == NUM_SCREENING_RECORDS

    # Verify each investigator belongs to the site recorded on the row.
    site_investigator_map = build_site_investigator_map(data["investigators"])
    invalid_pairs = screening_df[
        ~screening_df.apply(
            lambda row: row["investigator_id"]
            in site_investigator_map[row["site_id"]],
            axis=1,
        )
    ]
    assert invalid_pairs.empty, "Investigator/site mismatch detected."

    # Verify each site's country matches the country recorded on the row.
    site_country_map = dict(zip(data["sites"]["site_id"], data["sites"]["country_id"]))
    mismatched_countries = screening_df[
        screening_df["site_id"].map(site_country_map) != screening_df["country_id"]
    ]
    assert mismatched_countries.empty, "Site/country mismatch detected."

    save_csv(screening_df, "screening.csv", OUTPUT_DIR)

    print("Screening generation completed.")


if __name__ == "__main__":
    main()