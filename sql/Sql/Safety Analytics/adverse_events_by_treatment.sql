SELECT
    r.treatment_arm,
    COUNT(a.ae_id) AS adverse_events
FROM adverse_events_csv a
JOIN randomization_csv r
    ON a.randomization_id = r.randomization_id
GROUP BY r.treatment_arm
ORDER BY adverse_events DESC;