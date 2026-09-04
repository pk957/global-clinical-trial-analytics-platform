SELECT
    si.site_name,
    COUNT(sc.screening_id) AS screened_subjects
FROM screening sc
JOIN sites_csv si
    ON sc.site_id = si.site_id
GROUP BY si.site_name
ORDER BY screened_subjects DESC;