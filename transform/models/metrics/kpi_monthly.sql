-- Monthly trends with month-over-month volume change (Metabase "Monthly CSAT Trends")
with monthly as (
    select
        month,
        count(*)                                        as total_tickets,
        avg(first_response_minutes)                     as avg_first_response_minutes,
        avg(resolution_hours)                           as avg_resolution_hours,
        {{ pct_true('response_sla_met') }}              as response_sla_pct,
        {{ pct_true('resolution_sla_met') }}            as resolution_sla_pct,
        avg(csat_score)                                 as avg_csat
    from {{ ref('fct_tickets') }}
    group by month
)

select
    *,
    100.0 * (total_tickets - lag(total_tickets) over (order by month))
        / lag(total_tickets) over (order by month)      as volume_change_pct
from monthly
