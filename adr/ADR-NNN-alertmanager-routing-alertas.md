# ADR-003: Routing de alertas con Prometheus Alertmanager

**Fecha**: 2026-04-15
**Estado**: Aceptado

## Contexto

Se requieren alertas automáticas ante incumplimiento de KPIs (servicio caído, latencia alta, tasa de errores alta). Las reglas de alerta se definen en Prometheus, pero Prometheus por sí solo no envía notificaciones, requiere un componente separado que reciba las alertas y las enrute a los canales de notificación correspondientes.

## Alternativas consideradas

- **Grafana Unified Alerting (built-in)**: Grafana incluye su propio sistema de alertas con contact points configurables. Sin embargo, este sistema evalúa reglas definidas dentro de Grafana, no en Prometheus. Para recibir alertas disparadas por Prometheus, Grafana expone una API de Alertmanager que requiere autenticación: habría que generar un API token en Grafana, almacenarlo de forma segura y configurar Prometheus para incluirlo en cada request. Esto agrega pasos de configuración manuales y un secreto adicional a gestionar, sin ninguna ventaja funcional sobre Alertmanager.

- **Prometheus Alertmanager**: componente oficial del ecosistema Prometheus, diseñado específicamente para recibir alertas de Prometheus y enrutarlas. Se configura de forma declarativa en el YAML, soporta agrupamiento, silenciado, inhibición y múltiples receptores, como Slack o email. 

## Decisión

Se utiliza Prometheus Alertmanager como componente dedicado de routing de alertas. Prometheus envía las alertas a Alertmanager en el puerto 9093, y Alertmanager las enruta a Slack mediante un Incoming Webhook.

## Consecuencias

**Pros:**
- Componente oficial del ecosistema Prometheus, integración nativa y sin fricción
- Configuración declarativa en YAML, versionable junto al resto del stack
- Independiente de Grafana: el pipeline de alertas funciona aunque Grafana esté caído

**Contras:**
- Agrega un servicio más al docker-compose
- La versión v0.27.0 no soporta expansión de variables de entorno en la config, por lo que la URL del webhook de Slack se almacena en el archivo de configuración (excluido del repositorio vía `.gitignore`)
