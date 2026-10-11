-- Daily ticket volume with a 7-day rolling average. Every calendar day of the
-- years covered by the data is included (days with no tickets count as zero),
-- matching the date table in the Power BI model.
with days as (
    select generate_series(
        date_trunc('year', min(created_date)),
        date_trunc('year', max(created_date)) + interval '1 year - 1 day',
        interval '1 day'
    )::date as ticket_date
    from {{ ref('fct_tickets') }}
),

daily as (
    select created_date as ticket_date, count(*) as tickets
    from {{ ref('fct_tickets') }}
    group by created_date
)

select
    days.ticket_date,
    coalesce(daily.tickets, 0)                          as daily_tickets,
    avg(coalesce(daily.tickets, 0)) over (
        order by days.ticket_date
        rows between 6 preceding and current row
    )                                                   as rolling_7day_avg
from days
left join daily using (ticket_date)
