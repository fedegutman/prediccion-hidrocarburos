# Plataforma Predictiva de Hidrocarburos

Trabajo Integrador — Ingeniería de Software 2026.

Sistema para pronosticar producción de hidrocarburos por pozo. Fase 1: servicio mock con API REST, monitoreo y alertas.

## Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| API | 8000 | FastAPI — endpoints de forecast y pozos |
| Prometheus | 9090 | Recolección de métricas |
| Grafana | 3000 | Dashboard de monitoreo |
| Alertmanager | 9093 | Routing de alertas a Slack |
| node-exporter | 9100 | Métricas del host |

## Requisitos

- Docker
- Docker Compose

## Levantar el stack

```bash
docker compose up -d --build
```

## API

**Base URL**: `http://localhost:8000`

Autenticación: header `X-API-Key: abcdef12345`

### Endpoints

**GET /api/v1/forecast**
```
Params: id_well, date_start (YYYY-MM-DD), date_end (YYYY-MM-DD)
```

**GET /api/v1/wells**
```
Params: date_query (YYYY-MM-DD)
```

Documentación interactiva: [http://localhost:8000/docs](http://localhost:8000/docs)

## Monitoreo

### Grafana
URL: [http://localhost:3000](http://localhost:3000)  
Usuario: `admin` / Contraseña: `admin`

El dashboard **Oil & Gas Forecast API — Monitoreo** carga automáticamente con métricas de disponibilidad, latencia, tráfico y recursos del sistema.

### Prometheus
URL: [http://localhost:9090](http://localhost:9090)

- Reglas de alerta: `monitoring/prometheus/rules/alerts.yml`
- Estado de alertas: [http://localhost:9090/alerts](http://localhost:9090/alerts)

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

### Configurar Slack

1. Crear un Incoming Webhook en tu workspace de Slack
2. Copiar la URL del webhook en `monitoring/alertmanager/alertmanager.yml` (no commitear)

## Tests

```bash
# Instalar dependencias
poetry install

# Correr tests con cobertura
poetry run pytest --cov=app tests/
```

Cobertura actual: 100%

## Estructura del proyecto

```
├── app/
│   ├── main.py
│   ├── forecast/routes.py
│   └── wells/routes.py
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── rules/alerts.yml
│   ├── alertmanager/
│   │   └── alertmanager.yml        # no commitear — contiene el webhook de Slack
│   └── grafana/
│       ├── provisioning/
│       └── dashboards/
├── tests/
├── adr/
├── docker-compose.yaml
└── Dockerfile
```
