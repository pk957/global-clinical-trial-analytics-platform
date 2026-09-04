SELECT COUNT(*) AS total_studies
FROM studies;

SELECT COUNT(*) AS total_subjects
FROM subjects;

SELECT COUNT(*) AS total_randomized
FROM randomization_csv;

SELECT COUNT(*) AS total_sites
FROM sites_csv;

SELECT COUNT(*) AS total_countries
FROM countries_csv;

SELECT
    ROUND(
        100.0 *
        SUM(CASE WHEN study_status = 'Completed' THEN 1 ELSE 0 END)
        / COUNT(*),
        2
    ) AS completion_rate
FROM study_completion_csv;