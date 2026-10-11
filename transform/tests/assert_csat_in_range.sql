select ticket_id, csat_score
from {{ ref('fct_tickets') }}
where csat_score not between 1 and 5
