# Plataforma de Datos — Fase 2

Plataforma para integrar datos públicos de producción de hidrocarburos de [datos.gob.ar](https://datos.gob.ar) usando **arquitectura medallion** (Bronze → Silver → Gold).

> **Estado actual: Infraestructura base.**
> Está levantada la infra (Airflow + warehouse + dbt) y verificada la conexión, pero todavía
> **no hay datos ni transformaciones**: los schemas del warehouse existen vacíos. La extracción,
> el modelado y el resto se construyen en las próximas etapas (ver [Próximos pasos](#próximos-pasos)).

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
├── dags/                      # DAGs de Airflow (workflows) — vacío por ahora
├── ingestion/                 # helpers Python de extracción
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

## Próximos pasos

Lo que todavía falta construir:

- **Etapa 1** — Extracción → Bronze: DAG que baja los CSV de datos.gob.ar al schema `bronze`.
- **Etapas 2–3** — Modelos Silver y Gold (estrella) con dbt.
- **Etapa 4** — Calidad de datos con consecuencia operativa.
- **Etapa 5** — Backfill / reproceso por fecha.
- **Etapa 6** — Gobierno y lineage (DataHub).
- **Etapa 7** — BI con Metabase (dashboards para usuarios no técnicos).

Nota: La idea es ir actualizando este README a medida que avanzamos.
