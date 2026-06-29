{{ config(materialized='table') }}

-- Feature store OFFLINE (OBT): una fila por (idpozo × fecha_mes) con TODAS las features
-- (estado hasta el mes M) + el LABEL target_prod_pet_m1 (= prod_pet de M+1). Es la fuente del
-- TRAINING (que filtra target IS NOT NULL y hace split temporal). Materializado como TABLE para
-- que las features queden PERSISTIDAS (RNF-1) y reproducibles.
--
-- Reproducibilidad por fecha (RNF-3): con la var fecha_corte se filtra fecha_mes <= corte, de modo
-- que se puede reconstruir el feature set tal como estaba un día dado (ej. dbt build --vars '{fecha_corte: 2024-06-01}').

select
    fe.pozo_sk,
    fe.idpozo,
    fe.tiempo_sk,
    fe.fecha_mes,

    -- features autorregresivas de prod_pet
    fe.prod_pet_lag0,
    fe.prod_pet_lag1,
    fe.prod_pet_lag2,
    fe.prod_pet_lag3,
    fe.prod_pet_lag12,
    fe.prod_pet_ma3,
    fe.prod_pet_ma6,
    fe.prod_pet_ma12,
    fe.prod_pet_std3,
    fe.prod_pet_std6,
    (fe.prod_pet_lag0 - fe.prod_pet_lag1)                                as prod_pet_delta1,
    (fe.prod_pet_lag0 - fe.prod_pet_lag1) / nullif(fe.prod_pet_lag1, 0)  as prod_pet_pct1,

    -- covariables del mes M
    fe.prod_gas_m,
    fe.prod_agua_m,
    fe.prod_gas_m / nullif(fe.prod_pet_lag0, 0)                          as ratio_gas_pet,   -- GOR proxy
    fe.iny_agua_m,
    fe.iny_gas_m,
    fe.tef_m,
    fe.tef_ma3,
    fe.meses_en_produccion,

    -- estacionalidad (calendario del mes M, determinístico)
    dt.mes,
    dt.trimestre,

    -- atributos estáticos del pozo (dim_pozo, SCD Type 1). One-hot/scaling NO se persisten:
    -- son model-dependent y viven en la feature view junto al modelo.
    dp.cuenca,
    dp.provincia,
    dp.formacion_productiva,
    dp.tipo_reservorio,
    dp.profundidad,

    -- versión del esquema de features que espera el modelo (feature view versioning)
    'v1'::text                                                           as feature_set_version,

    -- LABEL (mes M+1)
    fe.target_prod_pet_m1

from {{ ref('feat_produccion_base') }} fe
join {{ ref('dim_tiempo') }} dt on dt.tiempo_sk = fe.tiempo_sk
join {{ ref('dim_pozo') }}   dp on dp.pozo_sk   = fe.pozo_sk
{% if var('fecha_corte', none) %}
where fe.fecha_mes <= '{{ var('fecha_corte') }}'::date
{% endif %}
