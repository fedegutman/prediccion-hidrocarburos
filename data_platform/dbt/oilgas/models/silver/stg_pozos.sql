-- Silver: listado maestro de pozos, limpio, tipado y DEDUPLICADO.
-- Grano: idpozo (UN registro por pozo). Insumo principal para dim_pozo en Gold.

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

),

-- Dedup: el maestro DEBE tener un registro por idpozo (grano de la dimensión), tal como
-- establece ADR-015 ("Silver limpia, tipa y deduplica"). bronze.pozos no trae fecha de
-- vigencia, así que el criterio de desempate es DETERMINÍSTICO y reproducible: ante un
-- idpozo repetido conservamos la fila MÁS COMPLETA (menos atributos NULL) y, si empatan,
-- un orden estable por atributos descriptivos. Así dim_pozo nunca recibe pozo_sk duplicada.
deduplicado as (

    select
        *,
        row_number() over (
            partition by idpozo
            order by
                num_nulls(sigla, formacion_productiva, area_yacimiento, cuenca,
                          provincia, tipo_reservorio, coordenadax, coordenaday,
                          cota, profundidad) asc,
                sigla nulls last,
                area_yacimiento nulls last,
                cuenca nulls last
        ) as rn
    from cleaned

)

select
    idpozo,
    id_empresa,
    sigla,
    formacion_productiva,
    area_yacimiento,
    cuenca,
    provincia,
    tipo_reservorio,
    coordenadax,
    coordenaday,
    cota,
    profundidad
from deduplicado
where rn = 1
