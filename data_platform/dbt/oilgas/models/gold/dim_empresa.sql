-- Dimensión empresa operadora. Grano: id_empresa.
-- Se construye desde las empresas vistas en producción (las que linkea la fact).

with produccion as (
    select * from {{ ref('stg_produccion') }}
)

select
    md5(coalesce(id_empresa, '__NA__')) as empresa_sk,
    coalesce(id_empresa, '__NA__')      as id_empresa,
    max(empresa)                        as empresa
from produccion
group by coalesce(id_empresa, '__NA__')
