# ADR-NNN: Stack de monitoreo: Prometheus + Grafana

**Fecha**: 2026-04-14
**Estado**: Aceptado

## Contexto

La Adenda Técnica Fase 1 requiere un dashboard de monitoreo que registre métricas de desempeño del sistema y métricas de negocio, con alertas automáticas ante incumplimiento de KPIs.

La adenda menciona explícitamente como opciones: "Grafana con Prometheus, o soluciones nativas de la nube".

## Alternativas consideradas

- **Amazon CloudWatch**: solución nativa de AWS, sin infraestructura adicional a gestionar. Sin embargo, introduce dependencia directa con AWS, y tiene costos asociados al volumen de métricas. Limita la portabilidad del sistema a otros entornos.

- **Prometheus + Grafana**: stack open source ampliamente usado en la industria. Se levanta junto con la API mediante docker-compose. Es portable, gratuito y no genera dependencia con ningún proveedor de nube. Prometheus recolecta métricas scrapeando el endpoint `/metrics` de la API cada 15 segundos, y Grafana las visualiza con dashboards y alertas configurables.

## Decisión

Se utiliza Prometheus + Grafana levantados con docker-compose junto al servicio de API. Es el stack que mejor se alinea con los requerimientos, es open source, portable y no genera dependencia de infraestructura externa.

## Consecuencias

**Pros:**
- Open source, sin costo
- Portable: funciona en cualquier entorno, no solo AWS
- Amplia documentación
- Se integra directamente con docker-compose junto a la API
- Grafana permite configurar dashboards y alertas de forma visual

**Contras:**
- Requiere gestionar dos servicios adicionales (Prometheus y Grafana)
- La persistencia de métricas depende del volumen montado en docker-compose
- Configuración inicial más manual que una solución nativa de nube
