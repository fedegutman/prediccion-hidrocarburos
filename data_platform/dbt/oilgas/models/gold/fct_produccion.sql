-- Fact de producción mensual por pozo. Grano: idpozo × anio × mes.
-- Las foreign keys son las MISMAS surrogate keys (md5) que generan las dimensiones,
-- recalculadas desde las claves naturales de cada fila → el join fact↔dim matchea.

with produccion as (
    select * from {{ ref('stg_produccion') }}
)

select
    -- foreign keys a las dimensiones
    md5(idpozo::text)                                   as pozo_sk,
    md5(coalesce(id_empresa, '__NA__'))                 as empresa_sk,   -- operadora de ese mes
    md5(concat_ws('|',
        coalesce(area_yacimiento, ''),
        coalesce(cuenca, ''),
        coalesce(provincia, '')))                       as area_sk,
    to_char(fecha_mes, 'YYYYMM')::int                   as tiempo_sk,

    -- claves degeneradas / contexto
    idpozo,
    anio,
    mes,
    fecha_mes,

    -- medidas
    prod_pet,
    prod_gas,
    prod_agua,
    iny_agua,
    iny_gas,
    iny_co2,
    iny_otro,
    tef
from produccion
