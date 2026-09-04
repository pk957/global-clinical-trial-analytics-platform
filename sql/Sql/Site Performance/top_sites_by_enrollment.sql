SELECT
    si.site_name,
    COUNT(s.subject_id) AS enrolled_subjects
FROM subjects s
JOIN sites_csv si
    ON s.site_id = si.site_id
GROUP BY si.site_name
ORDER BY enrolled_subjects DESC;