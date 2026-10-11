-- Escalation rate by category and priority, for groups with at least 20
-- tickets (Metabase "Escalation Risk Analysis")
select
    category,
    priority,
    count(*)                                            as total_tickets,
    count(*) filter (where is_escalated)                as escalated_count,
    {{ pct_true('is_escalated') }}                      as escalation_rate_pct,
    avg(resolution_hours) filter (where is_escalated)   as avg_escalated_resolution_hours
from {{ ref('fct_tickets') }}
group by category, priority
having count(*) >= 20
