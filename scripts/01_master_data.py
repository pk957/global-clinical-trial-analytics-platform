"""
01_master_data.py

Generates master/reference data for the Global Clinical Trial Analytics
Platform (Study CRC-GLB-301) and writes the resulting datasets to
data/raw/ as CSV files.

Outputs
-------
data/raw/studies.csv
data/raw/regions.csv
data/raw/countries.csv
data/raw/sites.csv
data/raw/investigators.csv

Author: Senior Data Engineering Team
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker
print("Script Started")


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

RANDOM_SEED = 42
OUTPUT_DIR = Path("data/raw")

STUDY_ID = "CRC-GLB-301"
PROTOCOL_NUMBER = "NVC-CRC-301"
SPONSOR = "NovaCura Therapeutics"
INVESTIGATIONAL_PRODUCT = "NVC-CRC101"
TARGET_ENROLLMENT = 6400
STUDY_STATUS = "Recruiting"

SITES_PER_COUNTRY = 8
INVESTIGATORS_PER_SITE = 2

ACTIVATION_DATE_START = date(2023, 1, 1)
ACTIVATION_DATE_END = date(2024, 12, 31)

# Region definitions
REGIONS = [
    {"region_code": "APAC", "region_name": "Asia Pacific"},
    {"region_code": "NAM", "region_name": "North America"},
    {"region_code": "EUR", "region_name": "Europe"},
    {"region_code": "AFR", "region_name": "Africa"},
]

# Countries with their region and ISO code, plus a Faker locale used to
# generate realistic, country-appropriate investigator names.
COUNTRIES = [
    {
        "country_id": "IND",
        "country_name": "India",
        "region_code": "APAC",
        "iso_code": "IN",
        "locale": "en_IN",
    },
    {
        "country_id": "SGP",
        "country_name": "Singapore",
        "region_code": "APAC",
        "iso_code": "SG",
        "locale": "en_US",
    },
    {
        "country_id": "USA",
        "country_name": "United States",
        "region_code": "NAM",
        "iso_code": "US",
        "locale": "en_US",
    },
    {
        "country_id": "CAN",
        "country_name": "Canada",
        "region_code": "NAM",
        "iso_code": "CA",
        "locale": "en_CA",
    },
    {
        "country_id": "GBR",
        "country_name": "United Kingdom",
        "region_code": "EUR",
        "iso_code": "GB",
        "locale": "en_GB",
    },
    {
        "country_id": "DEU",
        "country_name": "Germany",
        "region_code": "EUR",
        "iso_code": "DE",
        "locale": "de_DE",
    },
    {
        "country_id": "ZAF",
        "country_name": "South Africa",
        "region_code": "AFR",
        "iso_code": "ZA",
        "locale": "en_GB",
    },
    {
        "country_id": "KEN",
        "country_name": "Kenya",
        "region_code": "AFR",
        "iso_code": "KE",
        "locale": "en_US",
    },
]

SPECIALTY = "Medical Oncology"

# Cache of Faker instances keyed by locale so we do not re-instantiate them
_FAKER_CACHE: dict[str, Faker] = {}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def get_faker(locale: str) -> Faker:
    """Return a (cached) Faker instance for the given locale."""
    if locale not in _FAKER_CACHE:
        fkr = Faker(locale)
        fkr.seed_instance(RANDOM_SEED)
        _FAKER_CACHE[locale] = fkr
    return _FAKER_CACHE[locale]


def random_date(start: date, end: date) -> date:
    """Return a random date between start and end (inclusive)."""
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, delta_days))


# --------------------------------------------------------------------------
# Data generation functions
# --------------------------------------------------------------------------

def generate_studies() -> pd.DataFrame:
    """Generate the single-row studies.csv dataset."""
    study = {
        "study_id": STUDY_ID,
        "protocol_number": PROTOCOL_NUMBER,
        "study_title": (
            "A Global Phase III Randomized Double-Blind Placebo-Controlled Multi-Center Study Evaluating NVC-CRC101 in Subjects with Advanced Colorectal Cancer"
        ),
        "phase": "III",
        "therapeutic_area": "Oncology",
        "indication": "Advanced Colorectal Cancer",
        "study_design": "Randomized, Double-Blind, Placebo-Controlled, Multi-Center",
        "sponsor": SPONSOR,
        "investigational_product": INVESTIGATIONAL_PRODUCT,
        "comparator": "Standard of Care + Placebo",
        "start_date": date(2023, 3, 1).isoformat(),
        "end_date": date(2026, 12, 31).isoformat(),
        "target_enrollment": TARGET_ENROLLMENT,
        "study_status": STUDY_STATUS,
    }
    return pd.DataFrame([study])


def generate_regions() -> pd.DataFrame:
    """Generate the regions.csv dataset."""
    rows = []
    for region in REGIONS:
        rows.append(
            {
                "region_id": region["region_code"],
                "region_name": region["region_name"],
            }
        )
    return pd.DataFrame(rows)


def generate_countries() -> pd.DataFrame:
    rows = []

    for country in COUNTRIES:
        rows.append(
            {
                "country_id": country["country_id"],
                "region_id": country["region_code"],
                "country_name": country["country_name"],
                "iso_code": country["iso_code"],
            }
        )

    return pd.DataFrame(rows)


def generate_sites(countries_df: pd.DataFrame) -> pd.DataFrame:
    """Generate exactly 64 fictional oncology hospital sites (8 per country)."""
    rows = []
    site_counter = 1

    hospital_suffixes = [
        "Cancer Institute",
        "Oncology Center",
        "Comprehensive Cancer Center",
        "Regional Cancer Hospital",
        "Medical Center - Oncology Unit",
        "University Cancer Hospital",
        "General Hospital - Oncology Wing",
        "Specialist Cancer Clinic",
    ]

    for _, country in countries_df.iterrows():
        country_id = country["country_id"]
        country_name = country["country_name"]
        locale = next(
            c["locale"] for c in COUNTRIES if c["country_name"] == country_name
        )
        fkr = get_faker(locale)

        for i in range(SITES_PER_COUNTRY):
            city = fkr.city()
            suffix = hospital_suffixes[i % len(hospital_suffixes)]
            site_name = f"{city} {suffix}"
            activation_dt = random_date(ACTIVATION_DATE_START, ACTIVATION_DATE_END)

            rows.append(
                {
                    "site_id": f"SITE-{site_counter:04d}",
                    "study_id": STUDY_ID,
                    "country_id": country_id,
                    "site_name": site_name,
                    "city": city,
                    "activation_date": activation_dt.isoformat(),
                    "status": "Active",
                }
            )
            site_counter += 1

    return pd.DataFrame(rows)


def generate_investigators(sites_df: pd.DataFrame, countries_df: pd.DataFrame) -> pd.DataFrame:
    """Generate exactly 128 investigators (2 per site) with country-appropriate names."""
    rows = []
    investigator_counter = 1

    # Map country_id -> locale for name generation
    country_locale_map = {}
    for _, country in countries_df.iterrows():
        locale = next(
            c["locale"] for c in COUNTRIES if c["country_name"] == country["country_name"]
        )
        country_locale_map[country["country_id"]] = locale

    for _, site in sites_df.iterrows():
        site_id = site["site_id"]
        country_id = site["country_id"]
        locale = country_locale_map[country_id]
        fkr = get_faker(locale)

        for _ in range(INVESTIGATORS_PER_SITE):
            name = fkr.name()
            years_experience = random.randint(5, 30)
            gcp_certified = random.choices(
                ["Yes", "No"],
                weights=[95, 5],
                k=1,
            )[0]

            rows.append(
                {
                    "investigator_id": f"INV-{investigator_counter:04d}",
                    "site_id": site_id,
                    "investigator_name": name,
                    "specialty": SPECIALTY,
                    "years_experience": years_experience,
                    "gcp_certified": gcp_certified,
                }
            )
            investigator_counter += 1

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def save_dataframe(df: pd.DataFrame, filename: str, output_dir: Path) -> None:
    """Save a DataFrame to CSV in the specified output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / filename
    df.to_csv(file_path, index=False)
    print(f"Saved {len(df):>4} rows -> {file_path}")


# --------------------------------------------------------------------------
# Main orchestration
# --------------------------------------------------------------------------

def main() -> None:
    random.seed(RANDOM_SEED)

    studies_df = generate_studies()
    regions_df = generate_regions()
    countries_df = generate_countries()
    sites_df = generate_sites(countries_df)
    investigators_df = generate_investigators(sites_df, countries_df)

    # Referential integrity checks
    assert set(sites_df["country_id"]).issubset(set(countries_df["country_id"]))
    assert set(countries_df["region_id"]).issubset(
        {r["region_code"] for r in REGIONS}
    )
    assert set(investigators_df["site_id"]).issubset(set(sites_df["site_id"]))
    assert len(sites_df) == len(COUNTRIES) * SITES_PER_COUNTRY
    assert len(investigators_df) == len(sites_df) * INVESTIGATORS_PER_SITE

    save_dataframe(studies_df, "studies.csv", OUTPUT_DIR)
    save_dataframe(regions_df, "regions.csv", OUTPUT_DIR)
    save_dataframe(countries_df, "countries.csv", OUTPUT_DIR)
    save_dataframe(sites_df, "sites.csv", OUTPUT_DIR)
    save_dataframe(investigators_df, "investigators.csv", OUTPUT_DIR)

    print("\nMaster data generation complete.")


if __name__ == "__main__":
    main()