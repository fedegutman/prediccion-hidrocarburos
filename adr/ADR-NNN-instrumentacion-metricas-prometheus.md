# ADR-NNN: Instrumentación de métricas con prometheus-client

**Fecha**: 2026-04-14
**Estado**: Aceptado

## Contexto

Se requiere un dashboard de monitoreo que registre métricas de desempeño de la API REST (latencia, disponibilidad, uso de recursos) y las exponga para su visualización en Grafana vía Prometheus.

Para que Prometheus pueda recolectar métricas de la API, esta debe exponer un endpoint `/metrics` con datos en el formato que Prometheus entiende.

## Alternativas consideradas

- **prometheus-fastapi-instrumentator**: wrapper de terceros que integra automáticamente `prometheus-client` con FastAPI. Es una dependencia que no tiene el respaldo de la organización de Prometheus, la mantiene un desarrollador externo. Si ese desarrollador deja de actualizarla, la librería queda desactualizada o incompatible.

- **prometheus-client (oficial)**: librería oficial de Prometheus para Python. Requiere registrar las métricas manualmente mediante un middleware de FastAPI, pero elimina la dependencia de terceros y ofrece mayor control sobre qué métricas se exponen y cómo.

## Decisión

Se utiliza `prometheus-client` directamente, implementando un middleware en FastAPI que intercepta cada request para registrar:
- Total de requests por endpoint y status code (Counter)
- Latencia de respuesta por endpoint (Histogram)

## Consecuencias

**Pros:**
- Dependencia oficial de Prometheus, sin riesgo de abandono por terceros
- Control total sobre las métricas expuestas
- Sin overhead de abstracción innecesaria

**Contras:**
- Requiere más código manual que el wrapper
- Cualquier nueva métrica debe registrarse explícitamente
