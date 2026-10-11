select
    category,
    priority,
    total_tickets,
    escalated_count,
    round(escalation_rate_pct, 2)                   as escalation_rate,
    round(avg_escalated_resolution_hours::numeric, 1) as avg_escalated_resolution_time
from analytics.kpi_escalation
order by escalation_rate_pct desc
