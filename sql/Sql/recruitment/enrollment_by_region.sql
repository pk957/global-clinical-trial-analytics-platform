SELECT
    r.region_name,
    COUNT(s.subject_id) AS enrolled_subjects
FROM subjects s
JOIN countries_csv c
    ON s.country_id = c.country_id
JOIN regions_csv r
    ON c.region_id = r.region_id
GROUP BY r.region_name
ORDER BY enrolled_subjects DESC;    