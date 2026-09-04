SELECT
    r.treatment_arm,
    COUNT(*) AS serious_events
FROM adverse_events_csv a
JOIN randomization_csv r
    ON a.randomization_id = r.randomization_id
WHERE a.serious_event = 'Yes'
GROUP BY r.treatment_arm
ORDER BY serious_events DESC;Run git log --oneline -3 and git status --short. Report the output only. Do not modify, commit, or push anything.