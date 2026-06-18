-- Test de unicidad del grano de stg_produccion: una sola fila por (idpozo, anio, mes).
-- Test singular: si devuelve filas, el test FALLA (hay grano duplicado).

select
    idpozo,
    anio,
    mes,
    count(*) as filas
from {{ ref('stg_produccion') }}
group by idpozo, anio, mes
having count(*) > 1
