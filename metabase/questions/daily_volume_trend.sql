select
    ticket_date,
    daily_tickets,
    round(rolling_7day_avg, 2) as rolling_7day_avg
from analytics.kpi_daily_volume
order by ticket_date
