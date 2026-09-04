# Global Clinical Trial Analytics Platform

The Global Clinical Trial Analytics Platform is an end-to-end analytics project built on synthetic oncology clinical-trial data. It models the clinical-trial lifecycle from screening through study completion and supports analytical and stakeholder-facing reporting using Python, AWS data services, SQL, and Power BI Desktop.

> All records in this repository are synthetic. They do not represent real patients and must not be used for clinical decisions.

## Overview

The project contains a Python data-generation pipeline, related CSV datasets, validation checks, and a Power BI Desktop dashboard. The data supports recruitment, site-performance, safety, clinical-operations, treatment-efficacy, and geographic analysis.

## Technologies used

- Python and Faker
- CSV
- Amazon S3
- AWS Glue Data Catalog
- Amazon Athena
- SQL
- Power BI Desktop
- Git and GitHub

## Dataset

The project contains 14 related datasets:

- Studies
- Regions
- Countries
- Sites
- Investigators
- Screening
- Subjects
- Randomization
- Visits
- Laboratory Results
- Drug Dispensing
- Tumor Assessments
- Adverse Events
- Study Completion

## Data model

| Layer | Tables | Purpose |
| --- | --- | --- |
| Reference | `studies`, `regions`, `countries`, `sites`, `investigators` | Trial and operational hierarchy |
| Enrollment | `screening`, `subjects`, `randomization` | Candidate progression into the study |
| Clinical activity | `visits`, `laboratory_results`, `drug_dispensing`, `tumor_assessments` | Treatment and assessment history |
| Safety and disposition | `adverse_events`, `study_completion` | Safety surveillance and final subject status |

The relationships progress from studies and sites through screening, subjects, randomization, visits, and clinical fact tables. Each randomized subject has one study-completion record. A Death disposition requires a corresponding Fatal adverse event.

## Data pipeline

The Python scripts generate the datasets in dependency order:

1. `01_master_data.py`
2. `02_screening.py`
3. `03_subjects.py`
4. `04_randomization.py`
5. `05_visits.py`
6. `06_lab_results.py`
7. `07_drug_dispensing.py`
8. `08_tumor_assessments.py`
9. `09_adverse_events.py`
10. `10_study_completion.py`

Use the validation script to check the generated data without modifying it:

```powershell
python scripts/00_validate_pipeline.py
```

## Power BI Dashboard

The final Power BI Desktop dashboard is organized into four stakeholder-facing pages:

1. Executive Overview - overall trial performance, recruitment, population, geography, sites, investigators, and completion indicators.
2. Safety & Clinical Operations - adverse events, severity, treatment comparison, geography, and serious adverse-event timing.
3. Treatment Efficacy & Geography - tumor response trends and treatment-response consistency across regions.
4. Supporting Analysis - additional completion, screening, safety, and treatment-level analytical views.

### Dashboard Screenshots

- [Executive Overview](docs/powerbi/Executive_overview.png)
- [Safety & Clinical Operations](docs/powerbi/Safety&clinical_operations.png)
- [Treatment Efficacy & Geography](docs/powerbi/Treatment_efficacy&%20Geography.png)
- [Supporting Analysis](docs/powerbi/supporting_analysis.png)

## Analytics Workflow

1. Generate synthetic clinical-trial CSV datasets using Python.
2. Store the generated datasets in Amazon S3.
3. Catalogue the datasets using AWS Glue Data Catalog.
4. Define and query the analytical tables in Amazon Athena.
5. Develop SQL analyses and KPI queries in Athena.
6. Import the relevant datasets into Power BI Desktop for data modelling, analysis, and stakeholder-facing visualization.

## Setup

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Regenerate the full dataset
Get-ChildItem scripts\[0-9][0-9]_*.py | Sort-Object Name | ForEach-Object { python $_.FullName }
```

The generation scripts use fixed random seeds where appropriate. The `created_at` fields record when a script ran, so regenerating the dataset updates those timestamps.

## Repository structure

```text
.
|-- data/raw/                  # Generated synthetic CSV tables
|-- scripts/                   # Generators and read-only validation
|-- sql/                       # SQL analysis assets
|-- docs/
|   `-- powerbi/
|       |-- Executive_overview.png
|       |-- Safety&clinical_operations.png
|       |-- Treatment_efficacy& Geography.png
|       `-- supporting_analysis.png
|-- requirements.txt
`-- README.md
```

## Author

Prasanna Kumar
Data Analyst
