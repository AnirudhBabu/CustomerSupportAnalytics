WITH category_stats AS (
    SELECT 
        category,
        channel,
        COUNT(*) as volume,
        AVG(resolution_hours) as avg_resolution,
        COUNT(CASE WHEN resolution_sla_met = 1 THEN 1 END) * 100.0 / COUNT(*) as sla_rate
    FROM tickets
    WHERE status = 'Resolved'
    GROUP BY category, channel
)
SELECT 
    category,
    channel,
    volume,
    ROUND(avg_resolution, 2) as avg_resolution_hours,
    ROUND(sla_rate, 1) as sla_compliance_pct,
    CASE 
        WHEN avg_resolution < 12 AND sla_rate > 80 THEN 'Optimal'
        WHEN avg_resolution < 24 AND sla_rate > 60 THEN 'Acceptable'
        ELSE 'Needs Improvement'
    END as channel_fit
FROM category_stats
ORDER BY category, avg_resolution