{#- Small generic data tests, so the project needs no external packages. -#}

{% test row_count(model, expected) %}
select n from (select count(*) as n from {{ model }}) counted
where n != {{ expected }}
{% endtest %}

{% test unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as occurrences
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
