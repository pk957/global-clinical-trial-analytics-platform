SELECT
    c.country_name,
    COUNT(a.ae_id) AS adverse_events
FROM adverse_events_csv a
JOIN subjects s
    ON a.subject_id = s.subject_id
JOIN countries_csv c
    ON s.country_id = c.country_id
GROUP BY c.country_name
ORDER BY adverse_events DESC;