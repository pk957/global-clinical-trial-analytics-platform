SELECT
    treatment_arm,
    response_category,
    COUNT(*) AS total_subjects
FROM tumor_assessments t
JOIN randomization_csv r
    ON t.randomization_id = r.randomization_id
GROUP BY
    treatment_arm,
    response_category
ORDER BY
    treatment_arm,
    total_subjects DESC;