# ADR-024: Experiment Tracking y Model Registry (MLflow)

**Fecha**: 2026-06-28
**Estado**: Aceptado

## Contexto

La Adenda 3 exige (RF-2) una **plataforma de experiment tracking accesible a los ML Engineers** y (RF-3) que el **entrenamiento sea reproducible** (registrar runs con sus parámetros, métricas y versiones). El diagrama de la adenda incluye además un **Model Registry** entre Validation y el Servicio de API. Hace falta una herramienta que cubra ambas cajas y que, por la restricción de portabilidad del proyecto, **corra en la máquina de cualquier integrante y de los profesores** (Docker, sin servicio live, sin credenciales de nube).

## Alternativas consideradas

**Herramienta de tracking + registry:**
- **MLflow self-hosted (elegida):** tracking (runs, params, métricas, artefactos, git commit) + model registry (versiones, estados Staging/Production, alias, rollback) en **un solo servicio**. Es el default visto en clase (Clase 24). Open-source, se autohospeda en un contenedor, backend SQL + artifact store en disco. Cubre RF-2, RF-3 y el registry de una.
- **Weights & Biases:** excelente UI, pero es **SaaS externo** → requiere cuenta/API key y red saliente; rompe la portabilidad (no corre offline ni en la máquina del profesor sin credenciales) y deja datos fuera del control del TP.
- **DVC (experiments):** versiona datos/experimentos sobre git, pero **no trae UI de comparación de runs ni model registry con estados**; complementario, no sustituto.
- **Tracking casero (tabla en Postgres + carpeta de artefactos):** reinventa MLflow sin UI, sin registry, sin signatures; más código y menos robusto.

**Backend store (metadatos de runs/modelos):**
- **Base `mlflow` separada en el Postgres del warehouse (elegida):** reusa un contenedor que ya existe; no agrega RAM ni otro servicio; la base es lógicamente separada de `oilgas`.
- **Contenedor Postgres dedicado para MLflow:** más aislamiento pero otro contenedor/RAM; innecesario a esta escala.
- **SQLite en archivo:** simple pero no soporta concurrencia real ni es representativo.

**Artifact store (modelos serializados, etc.):**
- **Volumen Docker local (elegida):** persistente, **sin credenciales de nube** → corre en cualquier máquina. Coherente con la entrega sin servicio live.
- **Amazon S3:** lo canónico en producción, pero requiere credenciales AWS → rompe la portabilidad para compañeros/profesores y choca con la disciplina de costo del TP.

## Decisión

Se adopta **MLflow self-hosted** como Experiment Tracking + Model Registry, agregado como **servicio `mlflow` al `docker-compose` del `data_platform`** (imagen propia con `mlflow` y `psycopg2-binary` **pinneados**, ver `data_platform/mlflow/`):

- **Backend store:** base `mlflow` (separada) en el Postgres del **warehouse** (`postgresql://dwh:dwh@warehouse:5432/mlflow`); el contenedor la crea de forma idempotente al arrancar (funciona sobre volúmenes nuevos y existentes).
- **Artifact store:** **volumen Docker local** (`mlflow-artifacts`), servido por el propio tracking server (proxied artifacts), sin S3.
- **Acceso:** UI/API en `http://localhost:5500` (host 5500 para evitar el conflicto de AirPlay con 5000 en macOS).
- En **producción no se despliega** (la Fase 3 se entrega sin servicio live; se demuestra en el video corriendo en local).

## Consecuencias

**Pros:**
- Cubre RF-2 (UI de tracking para ML Engineers), RF-3 (runs reproducibles: params, métricas, git commit, versión de datos) y el Model Registry (versiones/estados/rollback) con una sola herramienta vista en clase.
- **Portable y reproducible:** corre con `docker compose up` en cualquier máquina, sin credenciales de nube ni instalaciones en el host; deps pinneadas.
- Reusa el Postgres existente (sin RAM extra de otra base) y persiste artefactos en un volumen local.
- Migración a S3/infra gestionada es un cambio de configuración (no de código) si en el futuro se quisiera.

**Contras / límites:**
- El artifact store local no es resiliente como S3 (un `docker compose down -v` borra el volumen); aceptable para el scope/demo.
- El backend compartido con el warehouse acopla ciclos de vida (mismo contenedor Postgres); mitigado por usar una base separada.
- `mlflow server` agrega ~150-250 MB de RAM al stack local (liviano, pero a tener en cuenta junto con Airflow).
