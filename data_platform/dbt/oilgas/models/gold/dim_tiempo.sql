-- Dimensión tiempo (mensual). Grano: un mes.
-- tiempo_sk = AAAAMM como entero (smart key legible para una dimensión de fecha).

with periodos as (
    select distinct anio, mes, fecha_mes
    from {{ ref('stg_produccion') }}
)

select
    to_char(fecha_mes, 'YYYYMM')::int     as tiempo_sk,
    fecha_mes,
    anio,
    mes,
    extract(quarter from fecha_mes)::int  as trimestre
from periodos
