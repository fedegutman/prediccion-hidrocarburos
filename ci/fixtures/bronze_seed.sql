-- Fixture de datos de prueba para el CI (NO son datos reales).
-- Crea la capa Bronze con un puñado de filas consistentes para que dbt construya
-- Silver/Gold y corra los tests de calidad sin depender de la ingesta real
-- (datos.gob.ar). Las columnas son las que consumen stg_pozos / stg_produccion.

create schema if not exists bronze;

drop table if exists bronze.pozos;
create table bronze.pozos (
    idpozo          bigint,
    idempresa       text,
    sigla           text,
    formprod        text,
    areayacimiento  text,
    cuenca          text,
    provincia       text,
    tipo_reservorio text,
    coordenadax     double precision,
    coordenaday     double precision,
    cota            double precision,
    profundidad     double precision
);

insert into bronze.pozos
    (idpozo, idempresa, sigla, formprod, areayacimiento, cuenca, provincia, tipo_reservorio, coordenadax, coordenaday, cota, profundidad)
values
    (1, 'EMP1', 'AB.x-1', 'Vaca Muerta', 'Loma Campana',     'Neuquina', 'Neuquén', 'NO CONVENCIONAL', -68.8, -38.5, 800, 2500),
    (2, 'EMP2', 'CD.x-2', 'Vaca Muerta', 'Fortin de Piedra', 'Neuquina', 'Neuquén', 'NO CONVENCIONAL', -69.1, -38.7, 850, 2600),
    (3, 'EMP1', 'EF.x-3', 'Mulichinco',  'El Trapial',       'Neuquina', 'Neuquén', 'CONVENCIONAL',    -69.5, -38.9, 900, 1800);

drop table if exists bronze.produccion;
create table bronze.produccion (
    idpozo           bigint,
    idempresa        text,
    anio             bigint,
    mes              bigint,
    prod_pet         double precision,
    prod_gas         double precision,
    prod_agua        double precision,
    iny_agua         double precision,
    iny_gas          double precision,
    iny_co2          double precision,
    iny_otro         double precision,
    tef              double precision,
    empresa          text,
    sigla            text,
    areayacimiento   text,
    cuenca           text,
    provincia        text,
    tipopozo         text,
    tipoestado       text,
    tipoextraccion   text,
    tipo_de_recurso  text,
    clasificacion    text,
    sub_tipo_recurso text,
    rectificado      text,
    habilitado       text
);

insert into bronze.produccion
    (idpozo, idempresa, anio, mes, prod_pet, prod_gas, prod_agua, iny_agua, iny_gas, iny_co2, iny_otro, tef,
     empresa, sigla, areayacimiento, cuenca, provincia, tipopozo, tipoestado, tipoextraccion, tipo_de_recurso, clasificacion, sub_tipo_recurso, rectificado, habilitado)
values
    (1,'EMP1',2024,1, 100.5, 50.2, 10.1, 0,0,0,0, 30.0, 'Empresa Uno','AB.x-1','Loma Campana','Neuquina','Neuquén','PETROLIFERO','EN PRODUCCION','SURGENCIA NATURAL','NO CONVENCIONAL','EXPLOTACION','SHALE','f','t'),
    (1,'EMP1',2024,2,  95.0, 48.0, 11.0, 0,0,0,0, 28.0, 'Empresa Uno','AB.x-1','Loma Campana','Neuquina','Neuquén','PETROLIFERO','EN PRODUCCION','SURGENCIA NATURAL','NO CONVENCIONAL','EXPLOTACION','SHALE','f','t'),
    (2,'EMP2',2024,1, 200.0,120.0,  5.0, 0,0,0,0, 31.0, 'Empresa Dos','CD.x-2','Fortin de Piedra','Neuquina','Neuquén','GASIFERO','EN PRODUCCION','SURGENCIA NATURAL','NO CONVENCIONAL','EXPLOTACION','SHALE','f','t'),
    (2,'EMP2',2024,2, 190.0,118.0,  6.0, 0,0,0,0, 30.0, 'Empresa Dos','CD.x-2','Fortin de Piedra','Neuquina','Neuquén','GASIFERO','EN PRODUCCION','SURGENCIA NATURAL','NO CONVENCIONAL','EXPLOTACION','SHALE','f','t'),
    (3,'EMP1',2024,1,  10.0,  5.0,  2.0, 0,0,0,0, 25.0, 'Empresa Uno','EF.x-3','El Trapial','Neuquina','Neuquén','PETROLIFERO','EN PRODUCCION','BOMBEO MECANICO','CONVENCIONAL','EXPLOTACION',null,'f','t');
