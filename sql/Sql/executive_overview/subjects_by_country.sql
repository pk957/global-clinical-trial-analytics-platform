SELECT
    c.country_name,
    COUNT(s.subject_id) AS enrolled_subjects
FROM subjects s
JOIN countries_csv c
    ON s.country_id = c.country_id
GROUP BY c.country_name
ORDER BY enrolled_subjects DESC;