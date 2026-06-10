-- Silver: producción mensual limpia y tipada.
-- Grano: idpozo × anio × mes. Lee de la capa Bronze (cargada por Airflow).

with source as (

    select * from {{ source('bronze', 'produccion') }}

),

cleaned as (

    select
        -- claves
        idpozo,
        nullif(trim(idempresa), '')                 as id_empresa,

        -- tiempo
        anio,
        mes,
        make_date(anio::int, mes::int, 1)           as fecha_mes,

        -- medidas de producción
        coalesce(prod_pet, 0)                       as prod_pet,
        coalesce(prod_gas, 0)                       as prod_gas,
        coalesce(prod_agua, 0)                      as prod_agua,

        -- medidas de inyección
        coalesce(iny_agua, 0)                       as iny_agua,
        coalesce(iny_gas, 0)                        as iny_gas,
        coalesce(iny_co2, 0)                        as iny_co2,
        coalesce(iny_otro, 0)                       as iny_otro,
        coalesce(tef, 0)                            as tef,

        -- atributos descriptivos (insumo para las dimensiones en Gold)
        nullif(trim(empresa), '')                   as empresa,
        nullif(trim(sigla), '')                     as sigla,
        nullif(trim(areayacimiento), '')            as area_yacimiento,
        nullif(trim(cuenca), '')                    as cuenca,
        nullif(trim(provincia), '')                 as provincia,
        nullif(trim(tipopozo), '')                  as tipo_pozo,
        nullif(trim(tipoestado), '')                as tipo_estado,
        nullif(trim(tipoextraccion), '')            as tipo_extraccion,
        nullif(trim(tipo_de_recurso), '')           as tipo_recurso,
        nullif(trim(clasificacion), '')             as clasificacion,
        nullif(trim(sub_tipo_recurso), '')          as sub_tipo_recurso,

        -- flags (texto 'f'/'t' en la fuente -> booleano)
        (lower(trim(rectificado)) = 't')            as rectificado,
        (lower(trim(habilitado)) = 't')             as habilitado

    from source

)

select * from cleaned
