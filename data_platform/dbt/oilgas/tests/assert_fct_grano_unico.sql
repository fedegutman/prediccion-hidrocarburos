-- Test de unicidad del grano de fct_produccion: una sola fila por (idpozo, anio, mes).
--
-- Defensa en profundidad: hoy fct_produccion es un select 1:1 de stg_produccion y hereda la
-- unicidad verificada en silver (assert_produccion_grano_unico). Este test la verifica en la
-- PROPIA capa Gold, así un join futuro que abra fan-out (1-a-muchos) se detecta acá y no
-- corrompe en silencio las métricas que consume el BI.
--
-- Severidad ERROR (default, a diferencia del test de completitud que es warn): un grano
-- duplicado NUNCA es válido y DEBE frenar el build.
--
-- Test singular: si devuelve filas, el test FALLA (hay grano duplicado).

select
    idpozo,
    anio,
    mes,
    count(*) as filas
from {{ ref('fct_produccion') }}
group by idpozo, anio, mes
having count(*) > 1
