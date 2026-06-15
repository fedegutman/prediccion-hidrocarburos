-- Dimensión tiempo (mensual). Grano: un mes.
--
-- Calendario DENSO: en vez de tomar solo los meses presentes en producción (select distinct,
-- que dejaría HUECOS si faltara un mes), generamos un  CONTIGUO entre el primer y el
-- último mes con datos. Una dimensión de fecha debe ser continua para análisis temporales
-- correctos
-- tiempo_sk = AAAAMM como entero (smart key); coincide con el que recalcula fct_produccion.

with bounds as (

    select
        date_trunc('month', min(fecha_mes))::date as desde,
        date_trunc('month', max(fecha_mes))::date as hasta
    from {{ ref('stg_produccion') }}
    where fecha_mes is not null

),

meses as (

    select generate_series(desde, hasta, interval '1 month')::date as fecha_mes
    from bounds

)

select
    to_char(fecha_mes, 'YYYYMM')::int     as tiempo_sk,
    fecha_mes,
    extract(year  from fecha_mes)::int    as anio,
    extract(month from fecha_mes)::int    as mes,
    extract(quarter from fecha_mes)::int  as trimestre
from meses
