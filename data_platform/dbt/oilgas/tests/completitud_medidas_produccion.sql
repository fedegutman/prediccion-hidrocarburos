-- Test de COMPLETITUD de las medidas de producción (Silver).
--
-- Severidad WARN (no ERROR): un NULL en una medida es legítimo (la operadora puede no
-- reportarla ese mes), así que NO rompemos el build. Pero avisamos si la completitud de
-- alguna medida cae por debajo del umbral: eso ya no es "sparsity" normal sino señal de
-- un problema de ingesta (ej. la fuente dejó de mandar una columna).
--
-- Un test singular de dbt "falla" cuando DEVUELVE filas. Acá solo devuelve fila para las
-- medidas cuya completitud está por debajo del umbral -> con severity=warn, eso se reporta
-- como WARN en el resumen de `dbt build` (PASS/WARN/ERROR) sin frenar la pipeline.
--
-- El umbral (0.30) es tuneable. count() ignora los NULL, así que con_dato = filas con valor.

{{ config(severity = 'warn') }}

with medidas as (
    select 'prod_pet'  as medida, count(*) as total, count(prod_pet)  as con_dato from {{ ref('stg_produccion') }}
    union all
    select 'prod_gas',  count(*), count(prod_gas)  from {{ ref('stg_produccion') }}
    union all
    select 'prod_agua', count(*), count(prod_agua) from {{ ref('stg_produccion') }}
    union all
    select 'iny_agua',  count(*), count(iny_agua)  from {{ ref('stg_produccion') }}
    union all
    select 'iny_gas',   count(*), count(iny_gas)   from {{ ref('stg_produccion') }}
    union all
    select 'iny_co2',   count(*), count(iny_co2)   from {{ ref('stg_produccion') }}
    union all
    select 'iny_otro',  count(*), count(iny_otro)  from {{ ref('stg_produccion') }}
    union all
    select 'tef',       count(*), count(tef)       from {{ ref('stg_produccion') }}
)

select
    medida,
    total,
    con_dato,
    round(100.0 * con_dato / nullif(total, 0), 1) as pct_completo
from medidas
where total > 0
  and con_dato::numeric / total < 0.30   -- umbral: < 30% completo => WARN
