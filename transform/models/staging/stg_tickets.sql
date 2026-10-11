-- Types every raw column. This is where text from the landing table becomes
-- real numbers, booleans and timestamps, and where missing values become NULL.
with source as (
    select * from {{ source('raw', 'tickets') }}
)

select
    ticket_id,
    created_date::timestamp                          as created_at,
    channel,
    category,
    priority,
    agent,
    team,
    first_response_minutes::double precision         as first_response_minutes,
    resolution_hours::double precision               as resolution_hours,
    status,
    nullif(resolved_date, '')::timestamp             as resolved_at,
    nullif(csat_score, '')::numeric::integer         as csat_score,
    region,
    country,
    -- kept only to cross-check the SLA flags derived in fct_tickets
    response_sla_met::boolean                        as source_response_sla_met,
    resolution_sla_met::boolean                      as source_resolution_sla_met
from source
