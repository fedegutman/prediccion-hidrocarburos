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
        -- Defensivo: si anio/mes vienen fuera de rango, devolvemos NULL en vez de dejar
        -- que make_date aborte TODO el build (silver+gold) con un error de fecha.
        case
            when anio between 1900 and 2100 and mes between 1 and 12
            then make_date(anio::int, mes::int, 1)
        end                                         as fecha_mes,

        -- medidas de producción (se PRESERVA NULL = "no reportado"; Silver limpia/tipa, no imputa)
        prod_pet,
        prod_gas,
        prod_agua,

        -- medidas de inyección (idem: NULL = ausencia de dato, distinto de un cero real)
        iny_agua,
        iny_gas,
        iny_co2,
        iny_otro,
        tef,

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
