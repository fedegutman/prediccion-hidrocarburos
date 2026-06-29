-- Consistencia TRAIN/SERVE: cada fila del online debe coincidir con la fila del offline
-- correspondiente al último mes de ese pozo (mismas feature columns). Si divergen, hubo
-- training-serving skew. Si devuelve filas, el test FALLA.

with latest as (
    select idpozo, max(fecha_mes) as fecha_mes
    from {{ ref('feat_produccion_offline') }}
    group by idpozo
)

select o.idpozo
from {{ ref('feat_produccion_online') }} o
join latest l  on l.idpozo = o.idpozo
join {{ ref('feat_produccion_offline') }} off
    on off.idpozo = o.idpozo and off.fecha_mes = l.fecha_mes
where o.fecha_mes           is distinct from off.fecha_mes
   or o.prod_pet_lag0       is distinct from off.prod_pet_lag0
   or o.prod_pet_ma3        is distinct from off.prod_pet_ma3
   or o.ratio_gas_pet       is distinct from off.ratio_gas_pet
   or o.meses_en_produccion is distinct from off.meses_en_produccion
   or o.feature_set_version is distinct from off.feature_set_version
