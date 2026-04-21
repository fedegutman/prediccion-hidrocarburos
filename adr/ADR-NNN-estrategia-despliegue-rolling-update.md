# ADR-NNN: Estrategia de despliegue: Rolling Update con Docker Compose

**Fecha**: 2026-04-19
**Estado**: Aceptado

## Contexto

El sistema debe desplegarse en ambientes de desarrollo, staging y producción con mínima interrupción del servicio. La consigna requiere implementar una estrategia de despliegue de bajo riesgo y recuperación automática ante fallos.

## Alternativas consideradas

- **Canary deployment**: dirigir un porcentaje del tráfico a la nueva versión antes de hacer el rollout completo. Requiere un load balancer con capacidad de routing por pesos (ej. AWS ALB), lo cual excede la infraestructura actual de EC2 + Docker Compose.
- **Blue/Green deployment**: mantener dos entornos idénticos y switchear el tráfico. Duplica el costo de infraestructura y agrega complejidad operativa innecesaria para la escala actual.
- **Rolling update con Docker Compose**: actualizar los contenedores de a uno manteniendo el servicio disponible durante la transición. Compatible con la infraestructura actual sin costo adicional.

## Decisión

Se utiliza rolling update mediante `docker compose up -d`, que reemplaza los contenedores uno a uno sin detener el servicio. El pipeline de CD incorpora un health check automático post-deploy que verifica que la API responda en `/health`. Si el health check falla, se restaura automáticamente la imagen anterior y se relanza el servicio.

## Consecuencias

**Pros:**
- Sin downtime durante el despliegue en condiciones normales
- Recuperación automática ante fallos sin intervención manual
- Compatible con la infraestructura existente sin costo adicional

**Contras:**
- Durante el rolling update pueden coexistir brevemente la versión anterior y la nueva (no es problema para una API stateless)
- No permite validar la nueva versión con un subconjunto del tráfico real antes del rollout completo (limitación respecto a canary)
