SELECT 
    category,
    priority,
    COUNT(*) as total_tickets,
    COUNT(CASE WHEN status = 'Escalated' THEN 1 END) as escalated_count,
    ROUND(COUNT(CASE WHEN status = 'Escalated' THEN 1 END) * 100.0 / COUNT(*), 2) as escalation_rate,
    AVG(CASE WHEN status = 'Escalated' THEN resolution_hours END) as avg_escalated_resolution_time
FROM tickets
GROUP BY category, priority
HAVING COUNT(*) >= 20
ORDER BY escalation_rate DESC