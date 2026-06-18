-- Validez del año (dimensión: validez).
--
-- anio ya tiene not_null, pero un año basura (0, negativo, 99999) pasaría ese test y
-- contaminaría dim_tiempo / fct_produccion. Acotamos a un rango razonable.
-- Severidad WARN: señal de calidad, no invariante estructural.
--
-- Devuelve los años fuera de rango (si los hubiera).

{{ config(severity = 'warn') }}

select distinct anio
from {{ ref('stg_produccion') }}
where anio < 1900 or anio > 2100
