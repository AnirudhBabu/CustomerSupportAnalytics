SELECT 
    agent,
    team,
    COUNT(*) as total_tickets,
    COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_count,
    ROUND(COUNT(CASE WHEN status = 'Resolved' THEN 1 END) * 100.0 / COUNT(*), 1) as resolution_rate,
    ROUND(AVG(resolution_hours), 2) as avg_resolution_time,
    ROUND(AVG(CASE WHEN csat_score IS NOT NULL THEN csat_score END), 2) as avg_csat,
    ROUND(COUNT(CASE WHEN response_sla_met = 1 THEN 1 END) * 100.0 / COUNT(*), 1) as frt_sla_compliance
FROM tickets
GROUP BY agent, team
HAVING COUNT(*) >= 50
ORDER BY resolution_rate DESC, avg_resolution_time ASC