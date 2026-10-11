-- Resolution performance of each channel for each issue category, resolved
-- tickets only (Metabase "Category Channel Performance")
with stats as (
    select
        category,
        channel,
        count(*)                                        as volume,
        avg(resolution_hours)                           as avg_resolution_hours,
        {{ pct_true('resolution_sla_met') }}            as resolution_sla_pct
    from {{ ref('fct_tickets') }}
    where is_resolved
    group by category, channel
)

select
    *,
    case
        when avg_resolution_hours < 12 and resolution_sla_pct > 80 then 'Optimal'
        when avg_resolution_hours < 24 and resolution_sla_pct > 60 then 'Acceptable'
        else 'Needs Improvement'
    end                                                 as channel_fit
from stats
