-- The ticket fact table every BI tool reads from. SLA flags are derived here
-- from the thresholds in dbt_project.yml so they have a single definition.
select
    ticket_id,
    created_at,
    created_at::date                                                    as created_date,
    channel,
    category,
    priority,
    case priority
        when 'Critical' then 1
        when 'High' then 2
        when 'Medium' then 3
        when 'Low' then 4
    end                                                                 as priority_rank,
    agent,
    team,
    first_response_minutes,
    resolution_hours,
    status,
    resolved_at,
    csat_score,
    region,
    country,
    first_response_minutes < {{ var('response_sla_minutes') }}          as response_sla_met,
    resolution_hours < {{ var('resolution_sla_hours') }}                as resolution_sla_met,
    status = 'Resolved'                                                 as is_resolved,
    status = 'Escalated'                                                as is_escalated,
    to_char(created_at, 'YYYY-MM')                                      as month,
    to_char(date_trunc('week', created_at), 'YYYY-MM-DD')
        || '/' || to_char(date_trunc('week', created_at) + interval '6 days', 'YYYY-MM-DD')
                                                                        as week,
    to_char(created_at, 'FMDay')                                        as day_of_week,
    extract(isodow from created_at)::integer                            as day_of_week_number,
    extract(hour from created_at)::integer                              as hour_of_day
from {{ ref('stg_tickets') }}
