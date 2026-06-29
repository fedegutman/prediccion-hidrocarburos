-- Point-in-time de los LABELS (multi-target): en la fila del mes M, target_prod_pet_m1 y
-- target_prod_gas_m1 deben ser la producción (pet/gas) de la fila del mes calendario siguiente
-- del MISMO pozo, en el panel denso. Verifica que el LEAD apuntó al mes M+1 REAL (horizonte 1)
-- y no saltó huecos. Si devuelve filas, el test FALLA.

select
    m.idpozo,
    m.fecha_mes,
    m.target_prod_pet_m1,
    nxt.prod_pet_lag0 as prod_pet_mes_siguiente,
    m.target_prod_gas_m1,
    nxt.prod_gas_m    as prod_gas_mes_siguiente
from {{ ref('feat_produccion_offline') }} m
join {{ ref('feat_produccion_offline') }} nxt
    on nxt.idpozo = m.idpozo
   and nxt.fecha_mes = (m.fecha_mes + interval '1 month')::date
where m.target_prod_pet_m1 is distinct from nxt.prod_pet_lag0
   or m.target_prod_gas_m1 is distinct from nxt.prod_gas_m
