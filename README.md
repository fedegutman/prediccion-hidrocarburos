# Plataforma Predictiva de Hidrocarburos

Trabajo Integrador — Ingeniería de Software 2026.

Sistema para pronosticar producción de hidrocarburos por pozo. Fase 1: servicio mock con API REST, monitoreo y alertas.

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

## Requisitos (ejecución local)

- Docker
- Docker Compose

## Levantar el stack localmente

```bash
# 1. Configurar Alertmanager (ver sección más abajo)
# 2. Levantar todos los servicios
docker compose up -d --build
```

## API

Autenticación: header `X-API-Key`. El valor se configura con la env var `API_KEY` (ver sección **Configuración**); **no hay default** — si no está seteada, la API responde 503.

### Endpoints

**GET /api/v1/forecast**
```
Params: id_well (string), date_start (YYYY-MM-DD), date_end (YYYY-MM-DD)
Response 200: { "id_well": "POZO-001", "data": [{ "date": "...", "prod": 150.5 }] }
Response 403: API key inválida
Response 400: date_end < date_start
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

> ⚠️ **Pendiente para prod:** el deploy (CD) todavía no inyecta `API_KEY`/`WAREHOUSE_DSN` en la instancia (hoy solo inyecta `API_IMAGE` y `SLACK_WEBHOOK_URL`). Falta sumarlas al paso de deploy + cargar los secrets, y definir dónde corre el warehouse en producción.

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

El deploy clona el repositorio en la instancia, inyecta las variables de entorno (`API_IMAGE`, `SLACK_WEBHOOK_URL`) y levanta el stack con `docker compose up -d`. Si el health check post-deploy falla, se restaura automáticamente la imagen anterior.

Las imágenes se almacenan en **Amazon ECR**. La autenticación de GitHub Actions con AWS se realiza via **OIDC** (sin credenciales estáticas), con roles IAM separados para CI (`GithubCIRole`) y CD (`InstanceCDRole`).

### Secrets de GitHub Actions

El pipeline requiere estos cuatro secrets (Settings → Secrets and variables → Actions). Los dos ARN salen de la infraestructura (`infra/terraform`, ver `terraform output`).

| Secret | Usado por | Para qué sirve |
|--------|-----------|----------------|
| `AWS_CI_ROLE_ARN` | CI (`build-and-scan`, `push`) | ARN del rol `GithubCIRole`. GitHub Actions lo asume via OIDC para autenticarse en ECR y pushear la imagen. |
| `AWS_CD_ROLE_ARN` | CD (`deploy-*`) | ARN del rol `InstanceCDRole`. GitHub Actions lo asume via OIDC para ejecutar el deploy en las EC2 via SSM. |
| `SLACK_WEBHOOK_URL` | CD | Incoming Webhook de Slack. Se inyecta en el `.env` de la instancia para que Alertmanager envíe las alertas al canal. |
| `GH_TOKEN` | CD | Personal Access Token con scope `repo`. El script de deploy lo usa para clonar el repositorio (privado) dentro de la instancia. |

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
│   ├── wells/routes.py
│   ├── metrics/
│   └── limiter.py
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
