-- Dimensión pozo (SCD Type 1: atributos actuales del maestro).
-- Grano: idpozo. Se cubren TODOS los pozos que aparecen en producción o en el maestro,
-- para que la fact nunca quede huérfana (sin dim).

with pozos as (
    select * from {{ ref('stg_pozos') }}
),

ids as (
    select idpozo from {{ ref('stg_produccion') }}
    union
    select idpozo from pozos
)

select
    md5(ids.idpozo::text)       as pozo_sk,      -- surrogate key (hash de la clave natural)
    ids.idpozo,
    p.sigla,
    p.formacion_productiva,
    p.area_yacimiento,
    p.cuenca,
    p.provincia,
    p.tipo_reservorio,
    p.coordenadax,
    p.coordenaday,
    p.cota,
    p.profundidad
from ids
left join pozos p on p.idpozo = ids.idpozo
