select agent, count(distinct team) as teams
from {{ ref('fct_tickets') }}
group by agent
having count(distinct team) > 1
