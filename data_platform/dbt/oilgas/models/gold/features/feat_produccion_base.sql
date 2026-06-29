{{ config(materialized='ephemeral') }}

-- Feature store — LÓGICA ÚNICA de features (single source of truth).
-- Es consumido por feat_produccion_offline (training) y, vía éste, por feat_produccion_online
-- (inferencia): así offline y online comparten EXACTAMENTE la misma transformación → no hay
-- training-serving skew (ver clase Feature Stores, ADR de Fase 3).
--
-- PANEL DENSO: cruce de cada pozo con los meses CONTIGUOS de dim_tiempo dentro de su rango
-- observado. Sin esto, un mes faltante correría las ventanas (lag1 tomaría M-2 creyéndolo M-1,
-- y el target apuntaría a M+3 creyéndolo M+1). Con el panel denso, lag(k) = exactamente k meses
-- calendario atrás y lead(1) = el mes calendario siguiente.
--
-- POINT-IN-TIME: toda feature usa SOLO información hasta el mes M (frames hacia atrás); las medias
-- y desvíos móviles EXCLUYEN el propio mes M (borde "1 preceding"). La ÚNICA columna que mira al
-- futuro es el label target_prod_pet_m1 (lead +1), que solo vive en el offline.

with bounds as (

    -- rango observado (primer y último mes con dato) de cada pozo
    select idpozo, min(fecha_mes) as desde, max(fecha_mes) as hasta
    from {{ ref('fct_produccion') }}
    group by idpozo

),

calendario_pozo as (

    -- panel denso: cada pozo × meses contiguos de dim_tiempo dentro de su rango
    select b.idpozo, t.fecha_mes, t.tiempo_sk
    from bounds b
    join {{ ref('dim_tiempo') }} t on t.fecha_mes between b.desde and b.hasta

),

base as (

    -- LEFT JOIN: los meses sin reporte quedan con medidas NULL (no se saltean → no corren la ventana)
    select
        c.idpozo,
        c.fecha_mes,
        c.tiempo_sk,
        md5(c.idpozo::text) as pozo_sk,
        f.prod_pet,
        f.prod_gas,
        f.prod_agua,
        f.iny_agua,
        f.iny_gas,
        f.tef
    from calendario_pozo c
    left join {{ ref('fct_produccion') }} f
        on f.idpozo = c.idpozo and f.tiempo_sk = c.tiempo_sk

)

select
    pozo_sk,
    idpozo,
    tiempo_sk,
    fecha_mes,

    -- prod_pet autorregresivo (lag0 = mes M = baseline naive de persistencia)
    prod_pet                                                                                              as prod_pet_lag0,
    lag(prod_pet, 1)  over w                                                                              as prod_pet_lag1,
    lag(prod_pet, 2)  over w                                                                              as prod_pet_lag2,
    lag(prod_pet, 3)  over w                                                                              as prod_pet_lag3,
    lag(prod_pet, 12) over w                                                                              as prod_pet_lag12,

    -- medias/desvíos móviles que EXCLUYEN el mes M (borde "1 preceding" = anti-leakage)
    avg(prod_pet)         over (partition by idpozo order by fecha_mes rows between 3  preceding and 1 preceding) as prod_pet_ma3,
    avg(prod_pet)         over (partition by idpozo order by fecha_mes rows between 6  preceding and 1 preceding) as prod_pet_ma6,
    avg(prod_pet)         over (partition by idpozo order by fecha_mes rows between 12 preceding and 1 preceding) as prod_pet_ma12,
    stddev_samp(prod_pet) over (partition by idpozo order by fecha_mes rows between 3  preceding and 1 preceding) as prod_pet_std3,
    stddev_samp(prod_pet) over (partition by idpozo order by fecha_mes rows between 6  preceding and 1 preceding) as prod_pet_std6,

    -- covariables del propio mes M (reportadas junto con la producción de M, conocidas al predecir M+1)
    prod_gas                                                                                             as prod_gas_m,
    -- gas autorregresivo (para el modelo de gas; multi-target). Mismo criterio point-in-time que prod_pet.
    lag(prod_gas, 1)  over w                                                                             as prod_gas_lag1,
    lag(prod_gas, 2)  over w                                                                             as prod_gas_lag2,
    lag(prod_gas, 3)  over w                                                                             as prod_gas_lag3,
    avg(prod_gas)        over (partition by idpozo order by fecha_mes rows between 3 preceding and 1 preceding) as prod_gas_ma3,
    prod_agua                                                                                            as prod_agua_m,
    iny_agua                                                                                             as iny_agua_m,   -- ver ADR: supuesto de disponibilidad al cierre de M
    iny_gas                                                                                              as iny_gas_m,
    tef                                                                                                  as tef_m,
    avg(tef)             over (partition by idpozo order by fecha_mes rows between 3 preceding and 1 preceding)   as tef_ma3,

    -- antigüedad: posición del mes en el panel denso del pozo (meses desde el primer dato, incluye huecos)
    row_number()         over w                                                                          as meses_en_produccion,

    -- LABELS: columnas forward (mes M+1). Solo en el offline; el online NO las lleva. Multi-target: petróleo y gas.
    lead(prod_pet, 1)    over w                                                                          as target_prod_pet_m1,
    lead(prod_gas, 1)    over w                                                                          as target_prod_gas_m1

from base
window w as (partition by idpozo order by fecha_mes)
