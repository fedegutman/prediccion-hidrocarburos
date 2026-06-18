# ADR-006: Estrategia de despliegue: reemplazo controlado con health check y rollback

**Fecha**: 2026-04-27
**Estado**: Aceptado

## Contexto

El sistema debe desplegarse en ambientes de desarrollo, staging y producción sobre instancias EC2, usando el stack contenerizado definido en `docker-compose.yaml`.

La infraestructura actual consiste en una instancia EC2 por ambiente, sin balanceador de carga ni múltiples réplicas de la API. El pipeline de CD ejecuta comandos remotos mediante AWS SSM, descarga la imagen publicada en Amazon ECR y levanta el stack con Docker Compose.

La unidad desplegable actual es el stack Docker Compose completo de cada ambiente. En runtime se observa una única réplica del servicio de API (`app-api-1`) y el `docker-compose.yaml` no define réplicas ni orquestación progresiva (`deploy.replicas`, Docker Swarm, ECS o Kubernetes). Por lo tanto, no existe una flota horizontal de instancias, servidores o pods sobre la cual aplicar un rollout por subconjuntos.

En este contexto, se necesita una estrategia de despliegue simple, reproducible y compatible con la infraestructura disponible para la Fase 1. Además, la Adenda Técnica requiere una estrategia de despliegue de bajo riesgo, verificación automática de salud tras el despliegue y recuperación automática en caso de falla.

## Alternativas consideradas

- **Canary deployment**: dirigir un porcentaje del tráfico a la nueva versión antes de hacer el rollout completo. Requiere un balanceador o gateway con capacidad de routing gradual por pesos, además de mantener simultáneamente al menos dos versiones del servicio. Esto excede la infraestructura actual de una EC2 por ambiente con Docker Compose.

- **Blue/Green deployment**: mantener dos entornos idénticos y switchear el tráfico desde el entorno activo hacia el entorno nuevo. Requiere duplicar infraestructura por ambiente y un mecanismo de cambio de tráfico, lo que agrega costo y complejidad operativa innecesaria para el alcance de la Fase 1.

- **Rolling update con múltiples réplicas**: actualizar instancias, servidores o pods progresivamente, manteniendo una parte de las réplicas anteriores disponible mientras entran las nuevas. Es una estrategia adecuada para fleets horizontales donde las instancias son intercambiables, pero requiere más de una réplica de la API y un mecanismo de orquestación o balanceo que no forma parte de la infraestructura actual.

- **Reemplazo directo sin validación**: descargar la nueva imagen y levantar el stack sin verificar salud ni conservar una versión anterior. Es simple, pero no cumple adecuadamente con la necesidad de bajo riesgo porque una imagen defectuosa podría quedar publicada sin recuperación automática.

- **Reemplazo controlado con Docker Compose + health check y rollback**: preservar localmente la imagen anterior, descargar la imagen correspondiente al ambiente, levantar el stack con `docker-compose up -d`, verificar `/health` y restaurar la imagen previa si la verificación falla. Es compatible con una sola instancia EC2 por ambiente y con el pipeline de CD vía SSM.

## Decisión

Se utiliza una estrategia de **reemplazo controlado con Docker Compose, health check HTTP post-deploy y rollback automático a la imagen anterior**.

Esta decisión se considera de bajo riesgo dentro de las restricciones de la Fase 1 porque reduce la probabilidad de dejar desplegada una versión defectuosa: la nueva imagen se descarga antes de detener el stack, el servicio se valida automáticamente después del despliegue y, ante falla, se restaura la imagen anterior. No se clasifica como rolling update porque no actualiza subconjuntos de una flota, sino la única unidad desplegable del ambiente.

El pipeline de CD se ejecuta luego de un workflow de CI exitoso. Según la rama que disparó el workflow (`develop`, `staging` o `main`), selecciona la instancia EC2 correspondiente mediante tags, se autentica en Amazon ECR, clona el repositorio en la instancia, genera el archivo `.env` con la imagen a desplegar y el webhook de Slack, y levanta el stack con `docker-compose up -d`.

Antes de descargar la nueva imagen, el pipeline lee la imagen actualmente configurada en `/app/.env` y, si existe localmente en Docker, la etiqueta como imagen de rollback (`<imagen-nueva>-rollback`). Luego genera la nueva configuración y ejecuta `docker-compose pull` antes de detener los contenedores actuales, para evitar bajar el servicio si la descarga de la imagen falla. Si la descarga es exitosa, detiene y elimina los contenedores existentes para evitar que queden procesos obsoletos o contenedores con configuración anterior, y levanta el stack actualizado.

Después de levantar la nueva versión, el pipeline espera hasta 60 segundos a que la API responda exitosamente en `http://localhost:8000/health`. Ese chequeo implementa la verificación automática de salud posterior al despliegue.

Si falla el despliegue o el health check, el pipeline restaura el `.env` apuntando a la imagen de rollback, vuelve a ejecutar `docker-compose up -d` y marca el workflow como fallido para dejar trazabilidad del incidente. Ese comportamiento implementa la recuperación automática ante falla del despliegue.

El rollback restaura la imagen Docker anterior disponible localmente. No revierte cambios de infraestructura ni cambios incompatibles en `docker-compose.yaml`.

## Consecuencias

**Pros:**
- Compatible con la infraestructura actual de una instancia EC2 por ambiente
- No requiere balanceador de carga ni orquestador adicional
- El despliegue es reproducible desde GitHub Actions mediante AWS SSM
- La imagen desplegada queda determinada explícitamente por la rama (`develop`, `staging` o `main`)
- Verifica automáticamente que la API responda después del despliegue
- Recupera automáticamente la versión anterior si la nueva imagen no queda saludable
- Evita describir como rolling update una infraestructura que no tiene réplicas ni flota horizontal

**Contras:**
- Puede haber una interrupción breve del servicio mientras se detienen los contenedores anteriores y se levantan los nuevos
- No ofrece downtime nulo ni rollout progresivo como un rolling update real
- El blast radius del despliegue es el ambiente completo, porque hay una sola réplica de API
- El rollback depende de que la imagen anterior exista localmente en la instancia
- Si el primer despliegue de un ambiente falla, no hay imagen previa disponible para restaurar
- No revierte cambios incompatibles de configuración o composición del stack
- No permite validar la nueva versión con un subconjunto del tráfico real antes del despliegue completo
