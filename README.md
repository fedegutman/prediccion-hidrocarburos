# Plataforma Predictiva de Hidrocarburos

Trabajo Integrador — Ingeniería de Software 2026.

Sistema para pronosticar producción de hidrocarburos por pozo, construido en tres fases:

- **Fase 1** — API REST (FastAPI) + stack de monitoreo (Prometheus/Grafana/Alertmanager) y CI/CD a AWS EC2.
- **Fase 2** — plataforma de datos: Airflow + data warehouse Postgres + dbt, arquitectura medallion (bronze/silver/gold).
- **Fase 3** — circuito de ML de punta a punta sobre `gold`: feature store + MLflow (tracking y model registry) + entrenamiento recurrente y automático, cuyas predicciones sirve la API.

## Ambientes

| Ambiente | API | Grafana | Prometheus |
|----------|-----|---------|------------|
| Producción | http://3.144.71.244:8000 | http://3.144.71.244:3000 | http://3.144.71.244:9090 |
| Staging | http://52.14.130.77:8000 | http://52.14.130.77:3000 | http://52.14.130.77:9090 |
| Desarrollo | http://18.222.31.105:8000 | http://18.222.31.105:3000 | http://18.222.31.105:9090 |

> Las IPs son públicas dinámicas: cambian si se apagan y vuelven a prender las instancias. Para refrescarlas: `cd infra/terraform && terraform output instance_public_ips`.

Documentación interactiva (Swagger): `<host>:8000/docs`

## Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| API | 8000 | FastAPI — endpoints de forecast y pozos |
| Prometheus | 9090 | Recolección de métricas |
| Grafana | 3000 | Dashboard de monitoreo |
| Alertmanager | 9093 | Routing de alertas a Slack |
| node-exporter | 9100 | Métricas del host |
| warehouse | interno | Postgres — data warehouse (capa gold) que sirve la API en prod |
| MLflow | 5500 | Experiment tracking + model registry (stack de datos `data_platform/`, corre local) |

## Requisitos (ejecución local)

- Docker
- Docker Compose

## Levantar el stack localmente

```bash
# 1. Configurar Alertmanager (ver sección más abajo)
# 2. Levantar todos los servicios
docker compose up -d --build
```

## Plataforma de datos (Fase 2)

### Arquitectura de datos
Arquitectura **medallion** sobre un data warehouse Postgres (`oilgas`):

```
datos.gob.ar ─(Airflow: bronze_ingesta)─▶ bronze ─(dbt)─▶ silver ─(dbt)─▶ gold ─┬─▶ API REST (/api/v1/produccion, /pozos)
                                          (crudo)        (limpio)     (estrella) └─▶ BI (Metabase)
```
- **Bronze**: dato crudo de las 2 fuentes (producción + maestro de pozos), cargado por Airflow.
- **Silver**: limpio, tipado, deduplicado (modelos dbt `stg_*`).
- **Gold**: modelo estrella (`fct_produccion` + `dim_pozo/empresa/area/tiempo`), listo para negocio. Ver [ADR-015](adr/ADR-015-arquitectura-medallion.md) y [ADR-017](adr/ADR-017-modelo-dimensional.md).
- **Calidad**: tests de dbt persistidos (`store_failures` → schema `dq_failures`); un test roto bloquea el deploy. Ver [ADR-019](adr/ADR-019-calidad-de-datos.md).

> **En producción:** corren la **API** + un **warehouse `gold` colocado** en la EC2. El pipeline (Airflow + dbt) y el **BI (Metabase)** corren **en local** (se demuestran en el video). Topología y alternativas en [ADR-021](adr/ADR-021-topologia-warehouse-produccion.md).

### Modelo estrella (Gold)

El diagrama de arriba es el **flujo** medallion; el **modelo estrella** de la capa `gold` (ERD) es el siguiente. Cardinalidad `||--o{` = una dimensión, muchas filas de hechos; las surrogate keys de la fact se recalculan con la misma fórmula que la dimensión (`md5(...)` / `AAAAMM`). Detalle y decisiones en [ADR-017](adr/ADR-017-modelo-dimensional.md).

```mermaid
erDiagram
    DIM_POZO    ||--o{ FCT_PRODUCCION : pozo_sk
    DIM_EMPRESA ||--o{ FCT_PRODUCCION : empresa_sk
    DIM_AREA    ||--o{ FCT_PRODUCCION : area_sk
    DIM_TIEMPO  ||--o{ FCT_PRODUCCION : tiempo_sk

    FCT_PRODUCCION {
        text   pozo_sk    FK "md5(idpozo)"
        text   empresa_sk FK "md5(id_empresa)"
        text   area_sk    FK "md5(area|cuenca|prov)"
        int    tiempo_sk  FK "AAAAMM"
        bigint idpozo     "grano"
        int    anio       "grano"
        int    mes        "grano"
        date   fecha_mes
        float  prod_pet   "medida"
        float  prod_gas   "medida"
        float  prod_agua  "medida"
        float  iny_agua   "medida"
        float  iny_gas    "medida"
        float  iny_co2    "medida"
        float  iny_otro   "medida"
        float  tef        "medida"
    }
    DIM_POZO {
        text   pozo_sk PK "md5(idpozo)"
        bigint idpozo
        text   sigla
        text   formacion_productiva
        text   area_yacimiento
        text   cuenca
        text   provincia
        text   tipo_reservorio
        float  coordenadax
        float  coordenaday
        float  cota
        float  profundidad
    }
    DIM_EMPRESA {
        text empresa_sk PK "md5(id_empresa)"
        text id_empresa
        text empresa
    }
    DIM_AREA {
        text area_sk PK "md5(area|cuenca|prov)"
        text area_yacimiento
        text cuenca
        text provincia
    }
    DIM_TIEMPO {
        int  tiempo_sk PK "AAAAMM"
        date fecha_mes
        int  anio
        int  mes
        int  trimestre
    }
```

### Levantar la plataforma de datos (local)
```bash
cd data_platform
docker compose up airflow-init      # una sola vez
docker compose up -d                # warehouse, Airflow, dbt, Metabase
```
- **Airflow** (orquestación): http://localhost:8080 (`airflow`/`airflow`) → correr el DAG `bronze_ingesta` para poblar Bronze; luego `dbt build` arma Silver/Gold y corre los tests.
- **Warehouse** (Postgres): `localhost:5433` (db `oilgas`, schemas `bronze`/`silver`/`gold`).

### Actualizar los workflows (DAGs)
Los DAGs son código en `data_platform/dags/`. Editar el `.py`, commitear y volver a levantar Airflow (`docker compose up -d`) — recarga los DAGs automáticamente.

### BI (Metabase)
Dashboard "Producción de Hidrocarburos" (producción por mes, top empresas, por cuenca):
- Local: http://localhost:3001 — se autoconfigura solo (servicio `metabase-init`), conectado al schema `gold`.
- En producción **corre solo en local** por decisión de costo/recursos (ver [ADR-021](adr/ADR-021-topologia-warehouse-produccion.md)); se demuestra en el video.

### Gobierno y linaje de datos
- **Linaje a nivel tabla + catálogo + descripciones** → **dbt docs** (`dbt docs generate` && `dbt docs serve`).
- **Workflows de extracción + última actualización de los datos** → **Airflow UI** (`localhost:8080`): DAGs, historial de runs y último run exitoso de cada uno.

Decisión y alternativas (DataHub) en [ADR-020](adr/ADR-020-gobierno-de-datos.md).

### Reprocesamiento / backfill
Procedimiento documentado y verificable en [docs/runbooks/data-engineer.md](docs/runbooks/data-engineer.md). La carga es **idempotente**: re-correr un período no duplica.

## Plataforma de ML (Fase 3)

Sobre la capa `gold` se monta un circuito de ML de punta a punta que cierra el flujo de la adenda (**Data Warehouse → Pre-proc/Training/Validation → Model Registry → API**), con orquestación (Airflow) y experiment tracking (MLflow):

```
gold (estrella)
   │  (dbt)
   ▼
Feature Store          offline  feat_produccion_offline  (con targets)  ─▶ entrenamiento
(dbt sobre gold)       online   feat_produccion_online   (sin targets)  ─┐ (scoring)
                                                                          │
Airflow  training_pipeline (@monthly)                                     │
   ├─ entrena modelo simple (petróleo + gas)                              │
   ├─ registra en MLflow  (tracking + model registry) ◀── Devs (ML Eng)   │
   └─ scoring batch sobre el online store ──▶ gold.fct_forecast ◀─────────┘
                                                    │
                                                    ▼
                                   API REST  GET /api/v1/forecast  ─▶ Usuarios
```

- **Feature store (dbt sobre gold)** → **RNF-1**. Las features quedan persistidas en dos tablas:
  - `feat_produccion_offline` — panel histórico (una fila por pozo × mes) **con los targets** (`target_prod_pet_m1`, `target_prod_gas_m1`), usado para entrenar.
  - `feat_produccion_online` — última fila por pozo **sin target**, usado para inferencia.
  - **Multi-target** (petróleo y gas) y **point-in-time / sin data leakage**: los lags miran solo hacia atrás y las medias móviles **excluyen el mes actual** (`rows between N preceding and 1 preceding`); los targets son el valor del mes siguiente (`lead`). Hay tests dbt que hacen cumplir la ausencia de leakage (`assert_feat_no_leakage_lag`, `assert_feat_ma_excludes_current`, `assert_feat_target_pointintime`).
- **Experiment tracking + model registry (MLflow)** → **RF-2**. Servicio propio en el `docker-compose` de la plataforma (corre local): UI en http://localhost:5500, *backend store* en Postgres y *artifact store* en un volumen Docker (sin dependencias de nube). Cada corrida loguea params y métricas, y los modelos se registran como `forecast_prod_pet` y `forecast_prod_gas` con alias `Production`. Ver [ADR-024](adr/ADR-024-experiment-tracking-model-registry.md).
- **Entrenamiento recurrente y automático (Airflow)**. El DAG `training_pipeline` corre `@monthly` y entrena ambos targets en paralelo con un modelo simple (`DecisionTreeRegressor`), los registra en MLflow y hace **scoring batch** sobre el online store, persistiendo las predicciones en `gold.fct_forecast`. El entrenamiento se puede repetir **para un día dado** (retrain) volviéndolo a triggerear desde Airflow.
- **API de predicciones**. `GET /api/v1/forecast` lee las predicciones de `gold.fct_forecast` por pozo, target y rango (ver sección **API**).

> **Encadenamiento de DAGs:** `bronze_ingesta → dbt_transform → training_pipeline` están acoplados por `ExternalTaskSensor` (no por trigger directo) y los tres corren `@monthly`. Para que el circuito se encadene de punta a punta, los tres deben ejecutarse con la **misma fecha lógica** (`logical_date`).

### Correr el circuito de ML (local)
```bash
cd data_platform
docker compose up airflow-init      # una sola vez
docker compose up -d                # warehouse + Airflow + dbt + MLflow + Metabase
docker compose ps                   # esperar a que todo esté "healthy"
```
1. **Airflow** (http://localhost:8080, `airflow`/`airflow`): activar y triggerear `bronze_ingesta` con config `{"date_from": "2023-01-01", "date_to": "2024-12-31"}`.
2. Al terminar, `dbt_transform` construye Silver/Gold + feature store con el gate de calidad; luego `training_pipeline` entrena y escribe `gold.fct_forecast`.
3. **MLflow** (http://localhost:5500): en *Models* deben aparecer `forecast_prod_pet` y `forecast_prod_gas`; en *Experiments*, las métricas de cada run.
4. La API sirve las predicciones: `GET /api/v1/forecast?...&target=prod_pet`.

### CI/CD de los pipelines de datos/ML
Los pipelines se validan en CI (ver sección **CI/CD**): `dbt-tests` (build + tests de calidad), `dbt-tests-red` (verifica que datos rotos **fallan** el gate), `ml-lint` (ruff + `py_compile` del training DAG y del job de ML) y `pages` (publica el catálogo de gobierno a GitHub Pages). Decisiones clave de Fase 3: [ADR-022](adr/ADR-022-gate-calidad-promocion-gold.md) (gate de calidad de datos), [ADR-023](adr/ADR-023-metadata-tecnica-de-carga-bronze.md) (metadata de carga en Bronze), [ADR-024](adr/ADR-024-experiment-tracking-model-registry.md) (MLflow), [ADR-025](adr/ADR-025-feature-store.md) (feature store), [ADR-026](adr/ADR-026-serving-predicciones.md) (serving de predicciones), [ADR-027](adr/ADR-027-gate-validacion-modelo.md) (gate de validación del modelo) y [ADR-028](adr/ADR-028-cicd-pipelines-datos-ml.md) (CI/CD de los pipelines de datos/ML). Decisiones de modelado: [ADR-029](adr/ADR-029-estrategia-horizonte-pronostico.md) (estrategia de horizonte de pronóstico), [ADR-030](adr/ADR-030-ubicacion-target-feature-store.md) (ubicación del target en el feature store) y [ADR-031](adr/ADR-031-nulos-estructurales-cold-start.md) (nulos estructurales y cold-start).

## API

Autenticación: header `X-API-Key`. El valor se configura con la env var `API_KEY` (ver sección **Configuración**); **no hay default** — si no está seteada, la API responde 503.

### Endpoints

**GET /api/v1/forecast** — predicciones del modelo ML (capa gold, `fct_forecast`)
```
Params: id_well (idpozo), date_start (YYYY-MM-DD), date_end (YYYY-MM-DD),
        target (prod_pet | prod_gas, def. prod_pet)
Response 200: { "id_well": "10001", "target": "prod_pet",
                "data": [{ "date": "2024-01-01", "prod": 150.5 }] }
Response 403: API key inválida | 400: date_end < date_start
Response 404: sin predicciones para el pozo/rango | 503: warehouse no disponible
```

**GET /api/v1/wells** _(deprecado — usar `/api/v1/pozos`)_
```
Params: date_query (YYYY-MM-DD)
Response 200: [{ "id_well": "POZO-001", ... }]   (datos MOCK de Fase 1)
Response 403: API key inválida
```

**GET /api/v1/produccion** — producción mensual real (capa gold)
```
Params: idpozo (opcional), anio (opcional), limit (1-1000, def. 100), offset
Response 200: [{ "idpozo", "anio", "mes", "fecha_mes", "empresa", "cuenca",
                 "provincia", "area_yacimiento", "prod_pet", "prod_gas", "prod_agua" }, ...]
Response 403: API key inválida | 503: warehouse no disponible
```

**GET /api/v1/pozos** — maestro de pozos real (capa gold)
```
Params: provincia (opcional), cuenca (opcional), limit (1-1000, def. 100), offset
Response 200: [{ "idpozo", "sigla", "formacion_productiva", "area_yacimiento",
                 "cuenca", "provincia", "tipo_reservorio", "profundidad" }, ...]
Response 403 | 503
```

**GET /api/v1/pozos/{idpozo}** — un pozo por id
```
Response 200: { ...pozo... } | 404: no existe | 403 | 503
```

**GET /health**
```
Response 200: { "status": "ok" }
```

## Configuración (variables de entorno)

La API se configura por variables de entorno, con defaults solo para desarrollo. **En producción se setean como secrets de GitHub** y el deploy las inyecta.

| Variable | Default (dev) | Descripción |
|----------|---------------|-------------|
| `API_KEY` | _(sin default — requerida)_ | Clave del header `X-API-Key`. **Debe** setearse (en prod, un valor secreto); si falta, la API responde 503. |
| `WAREHOUSE_DSN` | `postgresql://dwh:dwh@localhost:5433/oilgas` | Conexión read-only al data warehouse (capa gold). En prod apunta a la base real. |

- **Local sin Docker:** seteá `API_KEY` (no tiene default); el warehouse usa el default local:
  ```bash
  API_KEY=clave-local poetry run uvicorn app.main:app --reload
  ```
- **Local con Docker:** el contenedor alcanza el warehouse del host via `host.docker.internal:5433` (ya es el default en `docker-compose.yaml`).
- **Producción:** setear `API_KEY` y `WAREHOUSE_DSN`. El valor de `WAREHOUSE_DSN` depende de dónde se despliegue el warehouse.

> **Warehouse en producción:** corre como **contenedor `postgres:16` colocado** en la misma EC2 (en el `docker-compose` que despliega el CD), con config magra + `mem_limit` y un **swapfile** por el RAM de la t2.micro. El puerto no se expone: solo lo alcanza la API por la red interna. El `gold` se carga por **dump/restore** desde el pipeline (que corre local). Topología y alternativas en [ADR-021](adr/ADR-021-topologia-warehouse-produccion.md).

## CI/CD

El pipeline está dividido en dos workflows de GitHub Actions:

### CI (`CI.yml`) — se ejecuta en todo push y PR

| Job | Trigger | Descripción |
|-----|---------|-------------|
| `test` | Todo push y PR | Análisis estático (ruff) + tests con cobertura |
| `prometheus-rules` | Todo push y PR | Validación de reglas de alerta con promtool |
| `build-and-scan` | Push a develop/staging/main | Build de imagen Docker + escaneo de vulnerabilidades con Trivy + commit del reporte en `Reports/report.txt` |
| `push` | Push a develop/staging/main (después de `build-and-scan`) | Push de la imagen a Amazon ECR tageada con el nombre de la rama |

### CD (`CD.yml`) — se ejecuta cuando CI finaliza con éxito

| Job | Trigger | Descripción |
|-----|---------|-------------|
| `deploy-develop` | CI exitoso en `develop` | Deploy a EC2 `tp-development` via AWS SSM |
| `deploy-staging` | CI exitoso en `staging` | Deploy a EC2 `tp-staging` via AWS SSM |
| `deploy-prod` | CI exitoso en `main` | Deploy a EC2 `tp-production` via AWS SSM |

El deploy clona el repositorio en la instancia, inyecta las variables de entorno (`API_IMAGE`, `SLACK_WEBHOOK_URL`, `API_KEY`, `WAREHOUSE_DSN`), configura un **swapfile de 1 GB** (idempotente, por el RAM ajustado de la t2.micro — ver [ADR-021](adr/ADR-021-topologia-warehouse-produccion.md)) y levanta el stack con `docker compose up -d`. Si el health check post-deploy falla, se restaura automáticamente la imagen anterior.

Las imágenes se almacenan en **Amazon ECR**. La autenticación de GitHub Actions con AWS se realiza via **OIDC** (sin credenciales estáticas), con roles IAM separados para CI (`GithubCIRole`) y CD (`InstanceCDRole`).

### Pipelines de datos/ML (Fase 2/3)

Los pipelines de procesamiento (Airflow + dbt + entrenamiento) pasan por CI en cada push/PR: `dbt-tests` (build Silver/Gold + tests de calidad), `dbt-tests-red` (verifica que datos rotos **fallan** el gate), `ml-lint` (ruff + `py_compile` del training DAG y el job de ML) y `pages` (publica el catálogo de gobierno). El build de imagen se **gatea** con estos jobs. El "despliegue" del pipeline es **IaC versionada**: se levanta reproduciblemente con `docker compose` desde el código en git (los DAGs se recargan solos). **No se despliega a un runtime cloud** por decisión de scope (la Fase 3 se entrega **sin servicio live** y se demuestra en local) y de costo/recursos. Rationale y alternativas en [ADR-028](adr/ADR-028-cicd-pipelines-datos-ml.md) y [ADR-021](adr/ADR-021-topologia-warehouse-produccion.md).

### Secrets de GitHub Actions

El pipeline requiere estos secrets (Settings → Secrets and variables → Actions). Los dos ARN salen de la infraestructura (`infra/terraform`, ver `terraform output`).

| Secret | Usado por | Para qué sirve |
|--------|-----------|----------------|
| `AWS_CI_ROLE_ARN` | CI (`build-and-scan`, `push`) | ARN del rol `GithubCIRole`. GitHub Actions lo asume via OIDC para autenticarse en ECR y pushear la imagen. |
| `AWS_CD_ROLE_ARN` | CD (`deploy-*`) | ARN del rol `InstanceCDRole`. GitHub Actions lo asume via OIDC para ejecutar el deploy en las EC2 via SSM. |
| `SLACK_WEBHOOK_URL` | CD | Incoming Webhook de Slack. Se inyecta en el `.env` de la instancia para que Alertmanager envíe las alertas al canal. |
| `GH_TOKEN` | CD | Personal Access Token con scope `repo`. El script de deploy lo usa para clonar el repositorio (privado) dentro de la instancia. |
| `API_KEY` | CD | Clave del header `X-API-Key`. El deploy la inyecta en el `.env` de la instancia (la API responde 503 si falta). |
| `WAREHOUSE_DSN` | CD | DSN read-only al data warehouse (capa gold). El deploy lo inyecta en el `.env`; su valor depende de dónde corra el warehouse en prod. |

## Monitoreo

### Grafana
Usuario: `admin` / Contraseña: `admin`

El dashboard **Oil & Gas Forecast API — Monitoreo** carga automáticamente con métricas de disponibilidad, latencia, tráfico y recursos del sistema.

### Alertas configuradas

| Alerta | Condición | Severidad |
|--------|-----------|-----------|
| ServicioCaido | API sin responder por 1 minuto | critical |
| ErrorRateAlto | Tasa de errores 5xx > 1% por 2 minutos | warning |
| TasaAutenticacionFallida | Requests 403 > 0.5/seg por 2 minutos | warning |
| LatenciaForecastAlta | Latencia p95 > 5s por 2 minutos | warning |
| CPUAltaSostenida | CPU > 80% por 5 minutos | info |
| MemoriaAltaSostenida | Memoria > 85% por 5 minutos | info |

Las alertas se envían a Slack via Alertmanager.

### Configurar Slack (solo para ejecución local)

> En producción el webhook se inyecta automáticamente via CI/CD usando secrets de GitHub. Este paso solo es necesario si querés levantar el stack localmente.

1. Crear un Incoming Webhook en tu workspace de Slack
2. Copiar `monitoring/alertmanager/alertmanager.yml.template` a `monitoring/alertmanager/alertmanager.yml`
3. Reemplazar `${SLACK_WEBHOOK_URL}` con tu webhook real
4. El archivo `alertmanager.yml` está en `.gitignore` — no se commitea nunca

## Tests

```bash
# Instalar dependencias
poetry install

# Análisis estático
poetry run ruff check app/ tests/

# Correr tests con cobertura
poetry run pytest --cov=app tests/
```

Cobertura actual: 100%

## Estructura del proyecto

```
├── app/
│   ├── main.py
│   ├── forecast/routes.py
│   ├── wells/routes.py        # deprecado (mock Fase 1)
│   ├── pozos/routes.py        # API sobre gold
│   ├── produccion/routes.py   # API sobre gold
│   ├── db.py                  # acceso read-only al warehouse
│   ├── metrics/
│   └── limiter.py
├── data_platform/             # plataforma de datos (Fase 2) + ML (Fase 3)
│   ├── dags/                  # DAGs de Airflow (bronze_ingesta, dbt_transform, training_pipeline)
│   ├── dbt/oilgas/            # modelos dbt (silver/gold + feature store) + tests + dbt docs
│   ├── ml/                    # entrenamiento + scoring batch (tracer_bullet.py)
│   ├── mlflow/                # servicio MLflow (tracking + model registry)
│   ├── metabase/              # setup del BI
│   └── docker-compose.yaml
├── docs/runbooks/             # runbooks por rol (data-engineer, data-analyst)
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   ├── rules/alerts.yml
│   │   └── tests/alerts_test.yml
│   ├── alertmanager/
│   │   └── alertmanager.yml.template
│   └── grafana/
│       ├── provisioning/
│       └── dashboards/
├── tests/
├── adr/
├── Reports/
│   └── report.txt
├── .github/workflows/
│   ├── CI.yml
│   └── CD.yml
├── docker-compose.yaml
├── Dockerfile
├── poetry.lock
├── pyproject.toml
└── README.md
```

## ADRs

Las decisiones de arquitectura están documentadas en `/adr`:

| # | Decisión |
|---|----------|
| ADR-001 | API REST mock con FastAPI y OpenAPI |
| ADR-002 | Plataforma de cómputo: Amazon EC2 |
| ADR-003 | Registry de imágenes Docker: Amazon ECR |
| ADR-004 | Autenticación de GitHub Actions con AWS via OIDC |
| ADR-005 | Deploy remoto a EC2 via AWS SSM |
| ADR-006 | Estrategia de despliegue: reemplazo controlado con health check y rollback |
| ADR-007 | Escaneo de vulnerabilidades en imágenes Docker (Trivy) |
| ADR-008 | Stack de monitoreo: Prometheus + Grafana |
| ADR-009 | Instrumentación de métricas con prometheus-client |
| ADR-010 | Routing de alertas con Prometheus Alertmanager |
| ADR-011 | Canal de notificaciones: Slack |
| ADR-012 | Testing de reglas de alerta con promtool |
| ADR-013 | Decisiones de diseño del dashboard de Grafana |
| ADR-014 | Orquestación de datos con Airflow (DAGs como código) |
| ADR-015 | Arquitectura medallion (bronze / silver / gold) |
| ADR-016 | Tipo de carga (full vs incremental) |
| ADR-017 | Modelo dimensional (esquema estrella) |
| ADR-018 | Capa de servicio — API REST de solo lectura sobre Gold |
| ADR-019 | Estrategia de calidad de datos (dbt tests + store_failures + gate) |
| ADR-020 | Plataforma de gobierno y linaje (dbt docs + Airflow vs DataHub) |
| ADR-021 | Topología del warehouse en producción (contenedor colocado en EC2) |
| ADR-022 | Gate de calidad en la promoción a Gold (Write-Audit-Publish) |
| ADR-023 | Metadata técnica de carga por registro en Bronze |
| ADR-024 | Experiment tracking y model registry (MLflow) |
| ADR-025 | Feature store (offline + online sobre Gold con dbt) |
| ADR-026 | Serving de predicciones (scoring batch a `gold.fct_forecast`) |
| ADR-027 | Gate de validación del modelo antes de promover a Production |
| ADR-028 | CI/CD de los pipelines de datos/ML (validación en CI + ejecución local) |
| ADR-029 | Estrategia de horizonte de pronóstico (single-step M+1 con cap) |
| ADR-030 | Ubicación del target en el feature store (label en el offline) |
| ADR-031 | Manejo de nulos estructurales y cold-start en features |
