-- No-negatividad de las medidas en la FACT (defensa en profundidad sobre Gold).
--
-- Reespeja el test de silver (assert_medidas_no_negativas) pero sobre fct_produccion, para
-- que la barrera de validez viva también en la capa que consumen BI/ML — no solo aguas arriba.
-- Severidad WARN: una medida < 0 es señal de dato corrupto, lo visibilizamos sin frenar.
-- NULL no dispara (NULL < 0 es NULL).

{{ config(severity = 'warn') }}

select
    idpozo, anio, mes,
    prod_pet, prod_gas, prod_agua,
    iny_agua, iny_gas, iny_co2, iny_otro, tef
from {{ ref('fct_produccion') }}
where prod_pet  < 0 or prod_gas < 0 or prod_agua < 0
   or iny_agua  < 0 or iny_gas  < 0 or iny_co2   < 0
   or iny_otro  < 0 or tef      < 0
