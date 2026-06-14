-- Silver: listado maestro de pozos, limpio y tipado.
-- Grano: idpozo. Insumo principal para dim_pozo en Gold.

with source as (

    select * from {{ source('bronze', 'pozos') }}

),

cleaned as (

    select
        idpozo,
        nullif(trim(idempresa), '')              as id_empresa,
        nullif(trim(sigla), '')                  as sigla,
        nullif(trim(formprod), '')               as formacion_productiva,
        nullif(trim(areayacimiento), '')         as area_yacimiento,
        nullif(trim(cuenca), '')                 as cuenca,
        nullif(trim(provincia), '')              as provincia,
        nullif(trim(tipo_reservorio), '')        as tipo_reservorio,
        coordenadax,
        coordenaday,
        cota,
        profundidad
    from source

)

select * from cleaned
