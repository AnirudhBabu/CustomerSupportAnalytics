-- No ticket is lost or duplicated between the raw landing table and the fact table
select
    (select count(*) from {{ source('raw', 'tickets') }}) as raw_rows,
    (select count(*) from {{ ref('fct_tickets') }}) as fact_rows
where (select count(*) from {{ source('raw', 'tickets') }})
   <> (select count(*) from {{ ref('fct_tickets') }})
