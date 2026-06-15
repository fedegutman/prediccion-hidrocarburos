-- Dimensión geográfica: área/yacimiento + cuenca + provincia.
-- Grano: combinación distinta de (area_yacimiento, cuenca, provincia).
--
-- Normalizamos NULL -> '' UNA sola vez, de modo que el GROUP BY use EXACTAMENTE la misma
-- clave que la entrada del hash area_sk. Así NULL y '' dejan de ser grupos distintos y dos
-- grupos nunca pueden colapsar al mismo area_sk (lo que rompería el test unique).
-- fct_produccion arma area_sk con el mismo coalesce(...,''), así que el join fact<->dim
-- se mantiene consistente.

with produccion as (

    select
        coalesce(area_yacimiento, '') as area_yacimiento,
        coalesce(cuenca, '')          as cuenca,
        coalesce(provincia, '')       as provincia
    from {{ ref('stg_produccion') }}

)

select
    md5(concat_ws('|', area_yacimiento, cuenca, provincia)) as area_sk,
    area_yacimiento,
    cuenca,
    provincia
from produccion
group by area_yacimiento, cuenca, provincia
