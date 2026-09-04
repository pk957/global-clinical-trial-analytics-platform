SELECT
    screen_failure_reason,
    COUNT(*) AS total_failures
FROM screening
WHERE eligibility_status = 'Screen Failure'
GROUP BY screen_failure_reason
ORDER BY total_failures DESC;