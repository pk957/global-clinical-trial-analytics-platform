"""Validate the generated clinical-trial CSV dataset without modifying it.

Run from the repository root:
    python scripts/00_validate_pipeline.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DATA_DIR = Path("data/raw")

TABLES = {
    "studies": "studies.csv", "regions": "regions.csv", "countries": "countries.csv",
    "sites": "sites.csv", "investigators": "investigators.csv", "screening": "screening.csv",
    "subjects": "subjects.csv", "randomization": "randomization.csv", "visits": "visits.csv",
    "laboratory_results": "laboratory_results.csv", "drug_dispensing": "drug_dispensing.csv",
    "tumor_assessments": "tumor_assessments.csv", "adverse_events": "adverse_events.csv",
    "study_completion": "study_completion.csv",
}

PRIMARY_KEYS = {
    "studies": "study_id", "regions": "region_id", "countries": "country_id", "sites": "site_id",
    "investigators": "investigator_id", "screening": "screening_id", "subjects": "subject_id",
    "randomization": "randomization_id", "visits": "visit_id", "laboratory_results": "lab_result_id",
    "drug_dispensing": "dispensing_id", "tumor_assessments": "assessment_id", "adverse_events": "ae_id",
    "study_completion": "completion_id",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_fk(child: pd.DataFrame, child_column: str, parent: pd.DataFrame, parent_column: str, label: str) -> None:
    invalid = ~child[child_column].isin(parent[parent_column])
    require(not invalid.any(), f"{label}: {invalid.sum()} invalid reference(s).")


def load_tables() -> dict[str, pd.DataFrame]:
    """Load all expected tables, failing clearly if any are absent."""
    tables = {}
    for name, filename in TABLES.items():
        path = DATA_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required dataset is missing: {path}")
        tables[name] = pd.read_csv(path)
    return tables


def validate(tables: dict[str, pd.DataFrame]) -> None:
    """Validate identifiers, relationships, and the central clinical rules."""
    for table_name, primary_key in PRIMARY_KEYS.items():
        table = tables[table_name]
        require(primary_key in table, f"{table_name}: missing {primary_key} column.")
        require(table[primary_key].notna().all(), f"{table_name}: null {primary_key} value.")
        require(table[primary_key].is_unique, f"{table_name}: duplicate {primary_key} value.")

    studies, regions, countries, sites, investigators = (tables[name] for name in ("studies", "regions", "countries", "sites", "investigators"))
    screening, subjects, randomization, visits = (tables[name] for name in ("screening", "subjects", "randomization", "visits"))
    require_fk(countries, "region_id", regions, "region_id", "countries.region_id")
    require_fk(sites, "study_id", studies, "study_id", "sites.study_id")
    require_fk(sites, "country_id", countries, "country_id", "sites.country_id")
    require_fk(investigators, "site_id", sites, "site_id", "investigators.site_id")
    for column, parent, parent_column in (("study_id", studies, "study_id"), ("site_id", sites, "site_id"), ("investigator_id", investigators, "investigator_id"), ("country_id", countries, "country_id")):
        require_fk(screening, column, parent, parent_column, f"screening.{column}")
    require_fk(subjects, "screening_id", screening, "screening_id", "subjects.screening_id")
    require_fk(randomization, "subject_id", subjects, "subject_id", "randomization.subject_id")
    require_fk(visits, "randomization_id", randomization, "randomization_id", "visits.randomization_id")

    visit_subjects = visits.set_index("visit_id")["subject_id"]
    for name in ("laboratory_results", "drug_dispensing", "tumor_assessments", "adverse_events"):
        fact = tables[name]
        require_fk(fact, "visit_id", visits, "visit_id", f"{name}.visit_id")
        require_fk(fact, "subject_id", subjects, "subject_id", f"{name}.subject_id")
        require((fact["visit_id"].map(visit_subjects) == fact["subject_id"]).all(), f"{name}: subject_id does not match its visit_id.")

    completion = tables["study_completion"]
    require_fk(completion, "randomization_id", randomization, "randomization_id", "study_completion.randomization_id")
    require(completion["subject_id"].is_unique, "study_completion: each randomized subject must have one disposition record.")
    require(set(completion["subject_id"]) == set(randomization["subject_id"]), "study_completion: disposition records do not match randomized subjects.")
    fatal_subjects = set(tables["adverse_events"].loc[tables["adverse_events"]["outcome"] == "Fatal", "subject_id"])
    death_subjects = set(completion.loc[completion["study_status"] == "Death", "subject_id"])
    require(death_subjects <= fatal_subjects, "study_completion: Death requires a Fatal adverse event.")


def main() -> None:
    tables = load_tables()
    validate(tables)
    print(f"Validation passed: {len(tables)} tables and {sum(len(table) for table in tables.values()):,} total rows are consistent.")


if __name__ == "__main__":
    main()
