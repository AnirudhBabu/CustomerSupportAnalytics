{#- Shared KPI definitions. Every metrics model builds on these, so a KPI
    means the same thing on every dashboard. -#}

{# Share of rows where a boolean expression is true, as a percentage (0-100) #}
{% macro pct_true(condition) -%}
    100.0 * avg(case when {{ condition }} then 1 else 0 end)
{%- endmacro %}

{# Port of the Tableau "Agent Performance Score": 40% response SLA,
   40% resolution SLA, 20% CSAT/5. Rows without a CSAT score evaluate to
   NULL and are ignored by avg(), as they are in Tableau. #}
{% macro agent_performance_score() -%}
    avg(
        0.4 * case when response_sla_met then 1 else 0 end
        + 0.4 * case when resolution_sla_met then 1 else 0 end
        + 0.2 * csat_score / 5.0
    )
{%- endmacro %}
