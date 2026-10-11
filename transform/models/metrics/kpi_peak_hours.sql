-- Ticket volume by day of week and hour of day (Metabase "Peak Hours Analysis")
select
    day_of_week,
    day_of_week_number,
    hour_of_day,
    count(*)                                            as tickets
from {{ ref('fct_tickets') }}
group by day_of_week, day_of_week_number, hour_of_day
