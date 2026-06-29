# Plataforma de Datos — Fase 2

Pipeline de integración de datos de producción de hidrocarburos de [datos.gob.ar](https://datos.gob.ar),
con **arquitectura medallion** (Bronze → Silver → Gold) y consumo por **API REST** y **BI (Metabase)**.

> **Estado: pipeline completo de punta a punta.** Extracción (Airflow) → Bronze → Silver → Gold (dbt) →
> tests de calidad + gobierno (dbt docs) + BI (Metabase). Las decisiones clave están en los ADRs `014`–`021`.

## Componentes

| Componente | Herramienta | Rol |
|------------|-------------|-----|
| Orquestación | Apache Airflow 3.1.7 (CeleryExecutor) | Corre los DAGs (`bronze_ingesta`, `dbt_transform`) |
| Warehouse | PostgreSQL 16 | Aloja los schemas `bronze` / `silver` / `gold` |
| Transformación | dbt 1.8 (adapter postgres) | Construye Silver/Gold y corre los tests de calidad |
| BI | Metabase | Dashboards para usuarios no técnicos (sobre `gold`) |
| Gobierno / linaje | dbt docs + Airflow UI | Catálogo, linaje a nivel tabla, workflows y última actualización |
| Experiment tracking + model registry | MLflow | Tracking de runs de entrenamiento (RF-2/RF-3) y registro de modelos versionados (Fase 3, ver ADR-024) |

Las tres capas medallion (schemas del warehouse):

| Schema | Contenido |
|--------|-----------|
| `bronze` | Dato crudo de las 2 fuentes, tal cual viene (inmutable) |
| `silver` | Limpio, tipado, deduplicado — modelos dbt `stg_*` (vistas) |
| `gold` | Modelo estrella `fct_produccion` + `dim_pozo/empresa/area/tiempo` (tablas) |
| `dq_failures` | Filas que fallan un test de calidad (persistidas, ver ADR-019) |

> **Diagrama del esquema estrella (ERD):** ver [ADR-017](../adr/ADR-017-modelo-dimensional.md#diagrama-del-esquema-estrella) o el [README raíz](../README.md#modelo-estrella-gold).

> ℹ️ Hay **dos Postgres**: `postgres` es la base interna de Airflow (metadatos); `warehouse` es el data
> warehouse del proyecto. Separados a propósito.

## Requisitos

- Docker y Docker Compose
- ~6-7 GB de RAM libres para Docker (Airflow + warehouse + Metabase + dbt docs + MLflow)

## Levantar el stack

```bash
cd data_platform
docker compose up airflow-init        # setup inicial (una sola vez)
docker compose up -d --build          # Airflow + warehouse + Metabase + dbt docs + MLflow (--build construye la imagen de MLflow)
docker compose ps                  # esperar a que estén "healthy"
docker compose down                # apagar (mantiene los datos); -v para borrarlos
```

La primera vez tarda varios minutos: descarga imágenes e instala dbt dentro de los contenedores de Airflow
(ver `_PIP_ADDITIONAL_REQUIREMENTS` en `.env`).

## Accesos

| Servicio | URL / conexión | Credenciales |
|----------|----------------|--------------|
| Airflow (orquestación + workflows) | http://localhost:8080 | `airflow` / `airflow` |
| Metabase (BI) | http://localhost:3001 | `admin@oilgas.com` / `Admin1234!` |
| dbt docs (catálogo + linaje) | http://localhost:8082 | — |
| MLflow (tracking + model registry) | http://localhost:5500 | — |
| Warehouse (Postgres) | `localhost:5433`, db `oilgas` | `dwh` / `dwh` |

## Correr el pipeline

1. **Ingesta → Bronze:** en Airflow, activar y disparar el DAG **`bronze_ingesta`** (baja las 2 fuentes).
   ```bash
   docker compose exec airflow-scheduler airflow dags trigger bronze_ingesta
   # backfill de un rango puntual:
   docker compose exec airflow-scheduler airflow dags trigger bronze_ingesta \
     --conf '{"date_from":"2020-01-01","date_to":"2020-12-31"}'
   ```
2. **Transformar → Silver/Gold + tests:** el DAG **`dbt_transform`** corre `dbt build` al terminar la ingesta.
   También se puede a mano:
   ```bash
   docker compose exec airflow-scheduler dbt build --project-dir /opt/airflow/dbt/oilgas
   ```

## DAGs

| DAG | Qué hace | Propiedades |
|-----|----------|-------------|
| `bronze_ingesta` | Baja producción (merge por período) + maestro de pozos (full) a `bronze` | idempotente, retries con backoff, parametrizado por fecha (backfill) |
| `dbt_transform` | `dbt build` → Silver/Gold + tests; espera a que termine la ingesta | retries con backoff |

## Calidad de datos (ADR-019)

Tests de dbt (`not_null`, `unique`, `relationships`, `accepted_values` + tests singulares: grano único,
no-negatividad, rango de año). Cubren ≥3 dimensiones (completitud, validez, unicidad, integridad referencial,
schema). Las filas que fallan se **persisten** en el schema `dq_failures` (`store_failures`), y un test
estructural roto **bloquea el deploy** vía el job `dbt-tests` del CI.

## Gobierno y BI

- **Gobierno / linaje** → **dbt docs** (`http://localhost:8082`): catálogo de modelos, descripciones y linaje
  Bronze→Silver→Gold a nivel tabla. Workflows y última actualización → **Airflow UI**. (Decisión vs. DataHub en ADR-020.)
- **BI** → **Metabase** (`http://localhost:3001`): dashboard "Producción de Hidrocarburos" (por mes, por empresa,
  por cuenca), autoconfigurado por el servicio `metabase-init` contra el schema `gold`.

## Actualizar los workflows (DAGs)

Los DAGs son archivos Python en `dags/`. Al guardarlos, el `dag-processor` de Airflow los detecta
automáticamente (puede tardar unos segundos en la UI). No hace falta reiniciar.

## Estructura

```
data_platform/
├── docker-compose.yaml         # Airflow + warehouse + Metabase + dbt docs
├── .env                        # AIRFLOW_UID y librerías a instalar (dbt, pandas, requests)
├── dags/
│   ├── bronze_ingesta.py       #   DAG de ingesta a Bronze
│   ├── bronze_lib.py           #   helpers de descarga + carga al warehouse
│   └── dbt_transform.py        #   DAG que corre dbt build (Silver/Gold + tests)
├── warehouse/init/             # SQL de inicialización (schemas medallion)
├── metabase/setup_metabase.py  # autoconfiguración de Metabase (usuario, conexión, dashboards)
└── dbt/oilgas/                 # proyecto dbt
    ├── dbt_project.yml          #   schemas + store_failures + persist_docs
    ├── profiles.yml             #   conexión al warehouse
    ├── models/silver/           #   stg_produccion, stg_pozos (+ tests en _*.yml)
    ├── models/gold/             #   fct_produccion, dim_* (+ tests en _gold_models.yml)
    ├── tests/                   #   tests singulares (assert_*, completitud)
    └── macros/                  #   generate_schema_name (schemas medallion limpios)
```

## En producción

Corren la **API REST** + un **warehouse `gold` colocado** en la misma EC2 (Postgres magro, ver ADR-021).
El **pipeline (Airflow + dbt)** y el **BI (Metabase)** corren **en local** y se demuestran en el video —
no se despliegan a la nube por el límite de RAM de las instancias t2.micro.

## Decisiones (ADRs)

`014` orquestación · `015` medallion · `016` tipo de carga · `017` modelo dimensional ·
`018` API sobre Gold · `019` calidad · `020` gobierno · `021` topología del warehouse en prod.
Todos en [`../adr/`](../adr/), con comparación de alternativas.
