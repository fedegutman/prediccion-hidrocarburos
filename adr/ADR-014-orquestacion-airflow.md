# ADR-014: Orquestación de datos con Apache Airflow

**Fecha**: 2026-06-09
**Estado**: Aceptado

## Contexto

La Fase 2 requiere un proceso de extracción y procesamiento de datos en múltiples pasos (descarga de fuentes, carga a Bronze, transformaciones Silver/Gold, chequeos de calidad). La adenda exige una herramienta de orquestación con **DAGs definidos como código** (menciona explícitamente "Airflow / Prefect / Dagster / equivalente"), y que esos DAGs tengan **idempotencia, retries con backoff y observabilidad mínima (logs y status accesibles)**, además de permitir reprocesamiento histórico / backfill.

## Alternativas consideradas

- **Prefect**: orquestador moderno, liviano y muy pythónico, fácil de levantar. Tiene buen manejo de retries y una UI correcta, pero su modelo de lineage y observabilidad de datos es más débil, y no fue visto en clase.

- **Dagster**: orientado a *assets* de datos, con lineage nativo que se integraría bien con el requerimiento de gobierno. Es muy potente, pero introduce un modelo conceptual nuevo (software-defined assets) y es una herramienta no vista en clase.

- **Apache Airflow**: estándar de facto para orquestación, maduro y ampliamente documentado. Define DAGs como código Python (TaskFlow API), trae de forma nativa retries con backoff exponencial, scheduling, ejecución por intervalos de fecha y backfill, y una UI para ver el estado y los logs de cada tarea. Fue la herramienta vista en clase, por lo cual ya estabamos familiarizados con su uso.

## Decisión

Se utiliza **Apache Airflow** (versión 3.1.7, levantado con docker-compose) como herramienta de orquestación. Cumple todos los requisitos de la adenda de forma nativa (DAGs como código, retries con backoff, observabilidad de logs/status, backfill por fecha).

Los DAGs se definen con la TaskFlow API. La idempotencia se garantiza a nivel de cada tarea (reescribiendo particiones por fecha en lugar de insertar a ciegas), y el reprocesamiento se implementa mediante DAGs parametrizados por rango de fechas.

## Consecuencias

**Pros:**
- DAGs como código versionable, revisables en PRs
- Retries con backoff, scheduling y backfill nativos (no hay que implementarlos)
- UI con estado y logs por tarea → cubre la observabilidad mínima exigida

**Contras:**
- El compose con CeleryExecutor levanta ~7 contenedores (Redis, worker, scheduler, etc.): consumo de recursos elevado, especialmente al sumar otros servicios (DataHub, Metabase)
- El lineage de datos no es nativo: requiere integración externa (dbt + DataHub) para cumplir el requisito de gobierno
- Instalar dbt vía `_PIP_ADDITIONAL_REQUIREMENTS` reinstala en cada arranque (en producción convendría una imagen propia)
