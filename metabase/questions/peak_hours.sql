select
    day_of_week,
    hour_of_day,
    tickets
from analytics.kpi_peak_hours
order by day_of_week_number, hour_of_day
