WITH monthly_metrics AS (
    SELECT 
        strftime('%Y-%m', created_date) as month,
        COUNT(*) as total_tickets,
        AVG(first_response_minutes) as avg_frt,
        AVG(resolution_hours) as avg_resolution,
        COUNT(CASE WHEN response_sla_met = 1 THEN 1 END) * 100.0 / COUNT(*) as frt_sla,
        COUNT(CASE WHEN resolution_sla_met = 1 THEN 1 END) * 100.0 / COUNT(*) as resolution_sla,
        AVG(csat_score) as avg_csat
    FROM tickets
    GROUP BY month
)
SELECT 
    month,
    total_tickets,
    ROUND(avg_frt, 1) as avg_frt_minutes,
    ROUND(avg_resolution, 1) as avg_resolution_hours,
    ROUND(frt_sla, 1) as frt_sla_pct,
    ROUND(resolution_sla, 1) as resolution_sla_pct,
    ROUND(avg_csat, 2) as csat_score,
    ROUND(
        (total_tickets - LAG(total_tickets) OVER (ORDER BY month)) * 100.0 / 
        LAG(total_tickets) OVER (ORDER BY month), 
        1
    ) as volume_change_pct
FROM monthly_metrics
ORDER BY month