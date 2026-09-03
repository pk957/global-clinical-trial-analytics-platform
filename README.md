# Global Clinical Trial Analytics Platform

The Global Clinical Trial Analytics Platform is an end-to-end analytics project built on synthetic oncology clinical-trial data. It models the clinical-trial lifecycle from screening through study completion and supports analysis in AWS and Power BI.

> All records in this repository are synthetic. They do not represent real patients and must not be used for clinical decisions.

## Overview

The project contains a Python data-generation pipeline, related CSV datasets, validation checks, and a Power BI report. The data supports recruitment, site-performance, safety, clinical-operations, treatment-efficacy, and geographic analysis.

## Technologies used

- Python and Faker
- CSV
- Amazon S3
- AWS Glue Data Catalog
- Amazon Athena
- SQL
- Power BI
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

## Power BI report

The completed Power BI report is organized into four pages:

1. Executive Overview
2. Safety & Clinical Operations
3. Treatment Efficacy & Geography
4. Supporting Analysis

## AWS and Power BI workflow

1. Generate the synthetic CSV datasets.
2. Upload the files in `data/raw/` to Amazon S3.
3. Create or update tables in the AWS Glue Data Catalog.
4. Query the catalogued tables with Amazon Athena.
5. Connect Power BI to Athena and build the report from the related trial data.

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
|-- docs/                      # Project documentation
|-- requirements.txt
`-- README.md
```

## Author

Prasanna Kumar

Healthcare Data Analyst
