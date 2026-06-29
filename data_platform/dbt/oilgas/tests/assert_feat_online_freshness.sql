-- Freshness del online store: el mes máximo del online debe coincidir con el mes máximo de
-- fct_produccion. Detecta staleness (que la API sirva features viejas tras el último build).
-- Si devuelve filas, el test FALLA.

select
    o.fmax as online_max_mes,
    f.fmax as fct_max_mes
from (select max(fecha_mes) as fmax from {{ ref('feat_produccion_online') }}) o
cross join (select max(fecha_mes) as fmax from {{ ref('fct_produccion') }}) f
where o.fmax is distinct from f.fmax
