-- Anti-leakage de la MEDIA MÓVIL: prod_pet_ma3 NO debe incluir el mes M.
-- Cuando los tres meses previos (M-1, M-2, M-3) tienen dato, ma3 debe ser exactamente el
-- promedio de prod_pet_lag1, lag2 y lag3. Si incluyera M (o estuviera corrida), no coincidiría.
-- Si devuelve filas, el test FALLA.

select
    idpozo,
    fecha_mes,
    prod_pet_ma3,
    (prod_pet_lag1 + prod_pet_lag2 + prod_pet_lag3) / 3.0 as ma3_esperada
from {{ ref('feat_produccion_offline') }}
where prod_pet_lag1 is not null
  and prod_pet_lag2 is not null
  and prod_pet_lag3 is not null
  and abs(prod_pet_ma3 - (prod_pet_lag1 + prod_pet_lag2 + prod_pet_lag3) / 3.0) > 0.001
