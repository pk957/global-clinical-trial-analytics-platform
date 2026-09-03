# Clinical Trial Analytics Platform

## Overview

This project demonstrates an end-to-end healthcare data analytics pipeline using AWS and Power BI. A synthetic clinical trial dataset was generated to simulate real-world oncology clinical trials involving multiple countries, sites, investigators, subjects, laboratory results, adverse events, and treatment outcomes.

The project focuses on building scalable analytics workflows for recruitment monitoring, site performance, patient safety, and clinical operations.

---

## Project Architecture

Python (Faker)
        ↓
CSV Files
        ↓
Amazon S3
        ↓
AWS Glue Data Catalog
        ↓
Amazon Athena
        ↓
SQL Analytics
        ↓
Power BI Dashboard

---

## Technologies Used

- Python
- Faker
- Amazon S3
- AWS Glue
- Amazon Athena
- SQL
- Power BI
- Git & GitHub

---

## Dataset

The project contains 14 related datasets:

- Studies
- Subjects
- Investigators
- Sites
- Countries
- Regions
- Screening
- Visits
- Laboratory Results
- Drug Dispensing
- Tumor Assessments
- Randomization
- Adverse Events
- Study Completion

---

## Analytics Modules

### Executive Overview

- Total Studies
- Total Subjects
- Countries Participating
- Active Sites
- Enrollment Status
- Study Completion

---

### Recruitment Analytics

- Monthly Enrollment Trend
- Screening Success Rate
- Recruitment by Country
- Recruitment by Site
- Enrollment Growth

---

### Site Performance

- Subjects per Site
- Investigator Performance
- Visit Compliance
- Site Rankings

---

### Safety Analytics

- Adverse Events
- Serious Adverse Events
- Laboratory Abnormalities
- Safety Distribution

---

### Clinical Operations

- Drug Dispensing
- Treatment Arms
- Tumor Response
- Laboratory Monitoring
- Operational KPIs

---

## SQL

More than 50 analytical SQL queries were developed using Amazon Athena to support executive reporting and operational dashboards.

Topics include:

- Aggregations
- Joins
- Window Functions
- CASE Statements
- Ranking
- Date Analysis
- KPI Calculations

---

## Power BI Dashboard

Interactive dashboards include:

- Executive Overview
- Recruitment Analytics
- Site Performance
- Safety Dashboard
- Clinical Operations Dashboard

---

## Repository Structure

```
Clinical-Trial-Analytics/
│
├── data/
├── python/
├── sql/
├── powerbi/
├── screenshots/
└── README.md
```

---

## Future Improvements

- Predictive enrollment forecasting
- Risk-based monitoring
- Patient dropout prediction
- Machine learning integration
- Real-time dashboard automation

---

## Author

Prasanna Kumar

Healthcare Data Analyst
