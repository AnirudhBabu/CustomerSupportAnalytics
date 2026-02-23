SELECT 
    DATE(created_date) as ticket_date,
    COUNT(*) as daily_tickets,
    AVG(COUNT(*)) OVER (
        ORDER BY DATE(created_date) 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as rolling_7day_avg
FROM tickets
GROUP BY DATE(created_date)
ORDER BY ticket_date