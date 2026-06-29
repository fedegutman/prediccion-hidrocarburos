-- Anti-leakage del LAG: prod_pet_lag1 en la fila del mes M debe ser igual a prod_pet_lag0
-- (= prod_pet del mes M) de la fila del mes M-1 del MISMO pozo, en el panel denso.
-- Verifica que el lag mira exactamente un mes calendario atrás y NO salta huecos.
-- Si devuelve filas, el test FALLA.

select
    m.idpozo,
    m.fecha_mes,
    m.prod_pet_lag1,
    prev.prod_pet_lag0 as prod_pet_mes_anterior
from {{ ref('feat_produccion_offline') }} m
join {{ ref('feat_produccion_offline') }} prev
    on prev.idpozo = m.idpozo
   and prev.fecha_mes = (m.fecha_mes - interval '1 month')::date
where m.prod_pet_lag1 is distinct from prev.prod_pet_lag0
