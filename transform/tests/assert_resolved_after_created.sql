-- Resolved tickets have a resolution timestamp after creation; others have none
select ticket_id, status, created_at, resolved_at
from {{ ref('fct_tickets') }}
where (is_resolved and (resolved_at is null or resolved_at < created_at))
   or (not is_resolved and resolved_at is not null)
