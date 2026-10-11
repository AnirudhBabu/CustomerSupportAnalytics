-- Every KPI table must account for every ticket exactly once
with totals as (
    select 'kpi_summary' as model, (select tickets from {{ ref('kpi_summary') }}) as tickets
    union all select 'kpi_agent', (select sum(total_tickets) from {{ ref('kpi_agent') }})
    union all select 'kpi_daily_volume', (select sum(daily_tickets) from {{ ref('kpi_daily_volume') }})
    union all select 'kpi_monthly', (select sum(total_tickets) from {{ ref('kpi_monthly') }})
    union all select 'kpi_peak_hours', (select sum(tickets) from {{ ref('kpi_peak_hours') }})
)

select model, tickets, (select count(*) from {{ ref('fct_tickets') }}) as expected
from totals
where tickets is distinct from (select count(*) from {{ ref('fct_tickets') }})
