select
    month,
    total_tickets,
    round(avg_first_response_minutes::numeric, 1)   as avg_frt_minutes,
    round(avg_resolution_hours::numeric, 1)         as avg_resolution_hours,
    round(response_sla_pct, 1)                      as frt_sla_pct,
    round(resolution_sla_pct, 1)                    as resolution_sla_pct,
    round(avg_csat, 2)                              as csat_score,
    round(volume_change_pct, 1)                     as volume_change_pct
from analytics.kpi_monthly
order by month
