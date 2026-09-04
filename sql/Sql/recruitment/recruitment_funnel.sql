SELECT 'Screened' AS stage, COUNT(*) AS participants
FROM screening

UNION ALL

SELECT 'Eligible', COUNT(*)
FROM screening
WHERE eligibility_status = 'Eligible'

UNION ALL

SELECT 'Randomized', COUNT(*)
FROM randomization_csv

UNION ALL

SELECT 'Completed', COUNT(*)
FROM study_completion_csv
WHERE study_status = 'Completed';