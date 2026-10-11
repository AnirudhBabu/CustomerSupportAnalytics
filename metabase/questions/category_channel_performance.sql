select
    category,
    channel,
    volume,
    round(avg_resolution_hours::numeric, 2)         as avg_resolution_hours,
    round(resolution_sla_pct, 1)                    as sla_compliance_pct,
    channel_fit
from analytics.kpi_category_channel
order by category, avg_resolution_hours
