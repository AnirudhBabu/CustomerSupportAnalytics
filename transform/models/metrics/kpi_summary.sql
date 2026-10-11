-- Headline KPIs for the whole dataset (one row)
select
    count(*)                                            as tickets,
    avg(first_response_minutes)                         as avg_first_response_minutes,
    avg(resolution_hours)                               as avg_resolution_hours,
    {{ pct_true('response_sla_met') }}                  as response_sla_pct,
    {{ pct_true('resolution_sla_met') }}                as resolution_sla_pct,
    avg(csat_score)                                     as avg_csat,
    {{ pct_true('is_resolved') }}                       as resolution_rate_pct,
    {{ pct_true('is_escalated') }}                      as escalation_rate_pct,
    100.0 * sum(resolution_hours) filter (where is_escalated)
        / nullif(sum(resolution_hours), 0)              as escalated_share_of_resolution_hours_pct,
    {{ agent_performance_score() }}                     as agent_performance_score
from {{ ref('fct_tickets') }}
