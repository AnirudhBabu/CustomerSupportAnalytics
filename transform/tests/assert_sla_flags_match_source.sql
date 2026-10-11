-- The SLA flags derived from the thresholds in dbt_project.yml must agree with
-- the flags in the raw data. A mismatch means the thresholds have drifted.
select f.ticket_id
from {{ ref('fct_tickets') }} f
join {{ ref('stg_tickets') }} s using (ticket_id)
where f.response_sla_met <> s.source_response_sla_met
   or f.resolution_sla_met <> s.source_resolution_sla_met
