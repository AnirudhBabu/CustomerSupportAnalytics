select
    agent,
    team,
    total_tickets,
    resolved_count,
    round(resolution_rate_pct, 1)                   as resolution_rate,
    round(avg_resolution_hours::numeric, 2)         as avg_resolution_time,
    round(avg_csat, 2)                              as avg_csat,
    round(response_sla_pct, 1)                      as frt_sla_compliance,
    round(agent_performance_score, 3)               as agent_performance_score
from analytics.kpi_agent
order by resolution_rate_pct desc, avg_resolution_hours asc
