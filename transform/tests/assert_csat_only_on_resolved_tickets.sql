-- CSAT is collected only when a ticket is resolved, and always is then
select ticket_id, status, csat_score
from {{ ref('fct_tickets') }}
where is_resolved <> (csat_score is not null)
