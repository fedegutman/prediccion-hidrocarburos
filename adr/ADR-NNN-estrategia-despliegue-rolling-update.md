# ADR-NNN: Estrategia de despliegue: reemplazo controlado con health check y rollback

**Fecha**: 2026-04-27
**Estado**: Aceptado

## Contexto

El sistema debe desplegarse en ambientes de desarrollo, staging y producción sobre instancias EC2, usando el stack contenerizado definido en `docker-compose.yaml`.

La infraestructura actual consiste en una instancia EC2 por ambiente, sin balanceador de carga ni múltiples réplicas de la API. El pipeline de CD ejecuta comandos remotos mediante AWS SSM, descarga la imagen publicada en Amazon ECR y levanta el stack con Docker Compose.

En este contexto, se necesita una estrategia de despliegue simple, reproducible y compatible con la infraestructura disponible para la Fase 1. Además, la Adenda Técnica requiere verificación automática de salud tras el despliegue y recuperación automática en caso de falla.

## Alternativas consideradas

- **Canary deployment**: dirigir un porcentaje del tráfico a la nueva versión antes de hacer el rollout completo. Requiere un load balancer con capacidad de routing por pesos (ej. AWS ALB), lo cual excede la infraestructura actual de EC2 + Docker Compose.

- **Blue/Green deployment**: mantener dos entornos idénticos y switchear el tráfico. Duplica el costo de infraestructura y agrega complejidad operativa innecesaria para la escala actual.

- **Rolling update con múltiples réplicas**: actualizar instancias o contenedores progresivamente manteniendo réplicas anteriores disponibles mientras entran las nuevas. Requiere más de una réplica de la API o un mecanismo de orquestación/balanceo que no forma parte de la infraestructura actual.

- **Reemplazo controlado con Docker Compose + health check y rollback**: preservar localmente la imagen anterior, detener los contenedores actuales, descargar la imagen correspondiente al ambiente, levantar el stack con `docker-compose up -d`, verificar `/health` y restaurar la imagen previa si la verificación falla. Es compatible con una sola instancia EC2 por ambiente y con el pipeline de CD vía SSM.

## Decisión

Se utiliza una estrategia de reemplazo controlado con Docker Compose, health check HTTP post-deploy y rollback automático a la imagen anterior.

El pipeline de CD se ejecuta luego de un workflow de CI exitoso. Según la rama que disparó el workflow (`develop`, `staging` o `main`), selecciona la instancia EC2 correspondiente mediante tags, se autentica en Amazon ECR, clona el repositorio en la instancia, genera el archivo `.env` con la imagen a desplegar y el webhook de Slack, y levanta el stack con `docker-compose up -d`.

Antes de descargar la nueva imagen, el pipeline lee la imagen actualmente configurada en `/app/.env` y, si existe localmente en Docker, la etiqueta como imagen de rollback (`<imagen-nueva>-rollback`). Luego genera la nueva configuración y ejecuta `docker-compose pull` antes de detener los contenedores actuales, para evitar bajar el servicio si la descarga de la imagen falla. Si la descarga es exitosa, detiene y elimina los contenedores existentes para evitar que queden procesos obsoletos o contenedores con configuración anterior, y levanta el stack actualizado.

Después de levantar la nueva versión, el pipeline espera hasta 60 segundos a que la API responda exitosamente en `http://localhost:8000/health`. Si falla el despliegue o el health check, el pipeline restaura el `.env` apuntando a la imagen de rollback, vuelve a ejecutar `docker-compose up -d` y marca el workflow como fallido para dejar trazabilidad del incidente.

El rollback restaura la imagen Docker anterior disponible localmente. No revierte cambios de infraestructura ni cambios incompatibles en `docker-compose.yaml`.

## Consecuencias

**Pros:**
- Compatible con la infraestructura actual de una instancia EC2 por ambiente
- No requiere balanceador de carga ni orquestador adicional
- El despliegue es reproducible desde GitHub Actions mediante AWS SSM
- La imagen desplegada queda determinada explícitamente por la rama (`develop`, `staging` o `main`)
- Verifica automáticamente que la API responda después del despliegue
- Recupera automáticamente la versión anterior si la nueva imagen no queda saludable

**Contras:**
- Puede haber una interrupción breve del servicio mientras se detienen los contenedores anteriores y se levantan los nuevos
- El rollback depende de que la imagen anterior exista localmente en la instancia
- Si el primer despliegue de un ambiente falla, no hay imagen previa disponible para restaurar
- No revierte cambios incompatibles de configuración o composición del stack
- No permite validar la nueva versión con un subconjunto del tráfico real antes del despliegue completo
