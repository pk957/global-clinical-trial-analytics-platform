SELECT
    result_flag,
    COUNT(*) AS total_results
FROM laboratory_results
GROUP BY result_flag
ORDER BY total_results DESC;