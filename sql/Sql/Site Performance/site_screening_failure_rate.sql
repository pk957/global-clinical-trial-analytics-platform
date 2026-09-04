SELECT
    si.site_name,
    ROUND(
        100.0 * SUM(
            CASE
                WHEN sc.eligibility_status = 'Screen Failure' THEN 1
                ELSE 0
            END
        ) / COUNT(*),
        2
    ) AS screen_failure_rate
FROM screening sc
JOIN sites_csv si
    ON sc.site_id = si.site_id
GROUP BY si.site_name
ORDER BY screen_failure_rate DESC;