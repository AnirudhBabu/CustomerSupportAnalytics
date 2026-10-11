-- Agent productivity (Metabase "Agent Productivity" question)
select
    agent,
    team,
    count(*)                                            as total_tickets,
    count(*) filter (where is_resolved)                 as resolved_count,
    {{ pct_true('is_resolved') }}                       as resolution_rate_pct,
    avg(resolution_hours)                               as avg_resolution_hours,
    avg(csat_score)                                     as avg_csat,
    {{ pct_true('response_sla_met') }}                  as response_sla_pct,
    {{ agent_performance_score() }}                     as agent_performance_score
from {{ ref('fct_tickets') }}
group by agent, team
