{#
  Por defecto dbt antepone el schema del target al schema custom (ej: gold_silver).
  Con este override, el +schema de cada carpeta se usa tal cual: silver -> "silver", gold -> "gold".
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
