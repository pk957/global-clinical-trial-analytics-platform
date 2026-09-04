SELECT
    substr(enrollment_date, 1, 7) AS month,
    COUNT(*) AS enrolled
FROM subjects
GROUP BY substr(enrollment_date, 1, 7)
ORDER BY month;