SELECT
    visit_status,
    COUNT(*) AS total_visits
FROM visits
GROUP BY visit_status
ORDER BY total_visits DESC;