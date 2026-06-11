# Plataforma de Datos — Fase 2

Plataforma para integrar datos públicos de producción de hidrocarburos de [datos.gob.ar](https://datos.gob.ar) usando **arquitectura medallion** (Bronze → Silver → Gold).

> **Estado actual: Bronze.**
> Infra levantada (Airflow + warehouse + dbt) y **ingesta a Bronze funcionando**: el DAG
> `bronze_ingesta` baja las dos fuentes y las carga al schema `bronze`. Las capas Silver/Gold,
> la calidad, el gobierno y el BI se construyen en las próximas etapas (ver [Próximos pasos](#próximos-pasos)).

## Qué está montado hoy

| Componente | Herramienta | Rol |
|------------|-------------|-----|
| Orquestación | Apache Airflow 3.1.7 (CeleryExecutor) | Correr los workflows (DAGs) |
| Warehouse | PostgreSQL 16 | Aloja los schemas `bronze` / `silver` / `gold` (hoy vacíos) |
| Transformación | dbt 1.8 (adapter postgres) | Transformará Silver/Gold; ya conecta al warehouse |

Los tres schemas medallion ya existen en el warehouse:

| Schema | Propósito (cuando tenga datos) |
|--------|--------------------------------|
| `bronze` | Dato crudo tal cual viene de la fuente (inmutable) |
| `silver` | Dato limpio, tipado, deduplicado |
| `gold` | Modelo estrella (fact + dimensiones), listo para negocio |

> Hay **dos Postgres**: `postgres` es la base interna de Airflow (metadatos de orquestación);
> `warehouse` es el data warehouse del proyecto. Están separados a propósito.

## Requisitos

- Docker y Docker Compose
- ~4 GB de RAM libres para Docker

## Levantar el stack

```bash
cd data_platform

docker compose up airflow-init     # setup inicial (una sola vez)
docker compose up -d               # levanta todos los servicios

docker compose ps                  # ver estado (esperar a que estén "healthy")
docker compose down                # apagar (mantiene los datos)
docker compose down -v             # apagar y BORRAR los datos (volúmenes)
```

La primera vez tarda varios minutos: descarga imágenes e instala dbt dentro de los contenedores
de Airflow (ver `_PIP_ADDITIONAL_REQUIREMENTS` en `.env`).

## Accesos

| Servicio | URL / conexión | Credenciales |
|----------|----------------|--------------|
| Airflow (UI) | http://localhost:8080 | `airflow` / `airflow` |
| Warehouse (desde tu máquina) | `localhost:5433`, db `oilgas` | `dwh` / `dwh` |

## Estructura

```
data_platform/
├── docker-compose.yaml        # Airflow + warehouse + dbt
├── .env                       # AIRFLOW_UID y librerías a instalar
├── dags/                      # DAGs de Airflow (workflows)
│   ├── bronze_ingesta.py      #   DAG de ingesta a Bronze
│   └── bronze_lib.py          #   helpers de descarga + carga al warehouse
├── warehouse/init/            # SQL de inicialización (schemas medallion)
└── dbt/oilgas/                # proyecto dbt
    ├── dbt_project.yml
    ├── profiles.yml           # conexión al warehouse
    └── macros/
```

## Trabajar con dbt

dbt corre dentro de los contenedores de Airflow y transforma en el `warehouse`:

```bash
docker compose exec airflow-scheduler dbt debug --project-dir /opt/airflow/dbt/oilgas
docker compose exec airflow-scheduler dbt run   --project-dir /opt/airflow/dbt/oilgas
docker compose exec airflow-scheduler dbt test  --project-dir /opt/airflow/dbt/oilgas
```

## Actualizar los workflows (DAGs)

Los DAGs son archivos Python en `dags/`. Al guardarlos, el `dag-processor` de Airflow los detecta
automáticamente (puede tardar unos segundos en aparecer/actualizarse en la UI). No hace falta reiniciar.

## Ingesta a Bronze (DAG `bronze_ingesta`)

Baja las dos fuentes de datos.gob.ar y las aterriza crudas en el schema `bronze`:

| Fuente | Tabla destino | Tipo de carga |
|--------|---------------|---------------|
| Producción de pozos no convencional | `bronze.produccion` | Incremental, merge/upsert por período `(anio, mes)` |
| Listado de pozos por operadora | `bronze.pozos` | Full (reemplazo del snapshot) |

Está **parametrizado por rango de fechas** (`date_from` / `date_to`), lo que permite reprocesar un
período puntual (backfill). Por defecto carga la ventana **2023–2024** para que la demo sea rápida.
La carga de producción es **idempotente**: reejecutar el mismo rango no duplica datos. Ver `adr/ADR-016`.

```bash
# disparar con los parámetros por defecto (2023–2024)
docker compose exec airflow-scheduler airflow dags trigger bronze_ingesta

# disparar un rango específico (backfill)
docker compose exec airflow-scheduler airflow dags trigger bronze_ingesta \
  --conf '{"date_from": "2020-01-01", "date_to": "2020-12-31"}'
```

También se puede disparar desde la UI (http://localhost:8080).

## Capa Silver (dbt)

Modelos de limpieza/tipado sobre Bronze, materializados como **vistas** en el schema `silver`:

| Modelo | Origen | Grano |
|--------|--------|-------|
| `stg_produccion` | `bronze.produccion` | idpozo × anio × mes |
| `stg_pozos` | `bronze.pozos` | idpozo |

Tienen tests de calidad de dbt (`not_null`, `accepted_values`, `unique` + un test singular de unicidad de grano). Para construir/testear:

```bash
docker compose exec airflow-scheduler dbt run  --project-dir /opt/airflow/dbt/oilgas --select silver
docker compose exec airflow-scheduler dbt test --project-dir /opt/airflow/dbt/oilgas --select silver
```

## Capa Gold — modelo estrella (dbt)

Modelo dimensional materializado como **tablas** en el schema `gold` (ver `adr/ADR-017`):

| Modelo | Tipo | Grano |
|--------|------|-------|
| `fct_produccion` | fact | idpozo × anio × mes |
| `dim_pozo` | dimensión | idpozo |
| `dim_empresa` | dimensión | empresa operadora |
| `dim_area` | dimensión | área/yacimiento, cuenca, provincia |
| `dim_tiempo` | dimensión | mes |

Surrogate keys por hash (`md5` de la clave natural); SCD Type 1. Tests `relationships` garantizan integridad referencial fact↔dim.

```bash
docker compose exec airflow-scheduler dbt build --project-dir /opt/airflow/dbt/oilgas --select gold
```

## Próximos pasos

Lo que todavía falta construir:

- **Etapa 4** — Calidad de datos con consecuencia operativa.
- **Etapa 5** — Backfill / reproceso por fecha.
- **Etapa 6** — Gobierno y lineage (DataHub).
- **Etapa 7** — BI con Metabase (dashboards para usuarios no técnicos).

Nota: La idea es ir actualizando este README a medida que avanzamos.
