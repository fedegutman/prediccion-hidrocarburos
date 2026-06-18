-- No-negatividad de las medidas de producción/inyección en Silver (dimensión: validez).
--
-- Una producción o inyección NEGATIVA es físicamente imposible -> dato corrupto.
-- Severidad WARN: lo visibilizamos sin frenar el build (podría haber ajustes raros en la
-- fuente que convenga revisar antes de bloquear). Promovible a error si se confirma.
--
-- NULL no dispara (NULL < 0 es NULL, no true) -> solo cuenta negativos reales.
-- Devuelve una fila por cada registro con alguna medida < 0.

{{ config(severity = 'warn') }}

select
    idpozo, anio, mes,
    prod_pet, prod_gas, prod_agua,
    iny_agua, iny_gas, iny_co2, iny_otro, tef
from {{ ref('stg_produccion') }}
where prod_pet  < 0 or prod_gas < 0 or prod_agua < 0
   or iny_agua  < 0 or iny_gas  < 0 or iny_co2   < 0
   or iny_otro  < 0 or tef      < 0
