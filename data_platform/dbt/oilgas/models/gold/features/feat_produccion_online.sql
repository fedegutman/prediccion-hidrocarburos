{{ config(materialized='table') }}

-- Feature store ONLINE: snapshot "latest" = EXACTAMENTE una fila por pozo (su último mes con dato,
-- el mes M desde el cual se pronostica M+1), para lookup por idpozo en INFERENCIA (la API la lee).
--
-- Se construye SOBRE feat_produccion_offline (NO recalcula features): son las MISMAS filas/columnas
-- que vio el training, filtradas al último mes y SIN el label. Por construcción es imposible que la
-- lógica de features diverja entre train y serve → consistencia estructural (anti training-serving skew).

with ranked as (

    select
        *,
        row_number() over (partition by idpozo order by fecha_mes desc) as rn
    from {{ ref('feat_produccion_offline') }}

)

select
    pozo_sk,
    idpozo,
    tiempo_sk,
    fecha_mes,                 -- event_time: la API puede chequear freshness/TTL y degradar a baseline si es viejo
    prod_pet_lag0,
    prod_pet_lag1,
    prod_pet_lag2,
    prod_pet_lag3,
    prod_pet_lag12,
    prod_pet_ma3,
    prod_pet_ma6,
    prod_pet_ma12,
    prod_pet_std3,
    prod_pet_std6,
    prod_pet_delta1,
    prod_pet_pct1,
    prod_gas_m,
    prod_gas_lag1,
    prod_gas_lag2,
    prod_gas_lag3,
    prod_gas_ma3,
    prod_agua_m,
    ratio_gas_pet,
    iny_agua_m,
    iny_gas_m,
    tef_m,
    tef_ma3,
    meses_en_produccion,
    mes,
    trimestre,
    cuenca,
    provincia,
    formacion_productiva,
    tipo_reservorio,
    profundidad,
    feature_set_version
    -- NB: SIN target_prod_pet_m1 (en inferencia M+1 es justo lo que se predice)
from ranked
where rn = 1
