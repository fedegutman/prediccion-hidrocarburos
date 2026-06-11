-- Dimensión geográfica: área/yacimiento + cuenca + provincia.
-- Grano: combinación distinta de (area_yacimiento, cuenca, provincia).

with produccion as (
    select * from {{ ref('stg_produccion') }}
)

select
    md5(concat_ws('|',
        coalesce(area_yacimiento, ''),
        coalesce(cuenca, ''),
        coalesce(provincia, ''))) as area_sk,
    area_yacimiento,
    cuenca,
    provincia
from produccion
group by area_yacimiento, cuenca, provincia
