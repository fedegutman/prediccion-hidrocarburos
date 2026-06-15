# ADR-018: Capa de servicio — API REST de solo lectura sobre Gold

**Fecha**: 2026-06-15
**Estado**: Aceptado

## Contexto

La Fase 2 integró los datos reales en el warehouse (modelo estrella en el schema `gold`, ver [ADR-017](ADR-017-modelo-dimensional.md)). El PRD y la adenda exigen una **API REST para el acceso programático a los datos**, consumible por sistemas externos (caso de uso "Integración en Sistemas Externos"). Hasta ahora la API (Fase 1) servía **datos mock** (`app/mock_data.py`), desconectada del warehouse.

Hay que decidir **cómo exponer Gold por API**: dónde corre, dónde vive la lógica de negocio, qué forma tienen los endpoints, cómo se conecta entre entornos (local / contenedor / nube) y con qué nivel de acceso. La capa de servicio es un consumidor de Gold; no debe reimplementar lo que ya resuelve la plataforma de datos.

## Alternativas consideradas

**1. Dónde implementar la API de datos**
- **Servicio/API nueva y separada** solo para datos: aísla el dominio de datos, pero duplica infraestructura ya resuelta en Fase 1 (auth, rate-limiting, métricas, CI/CD, deploy) y agrega un servicio más para operar, sin beneficio claro a esta escala.
- **Que el BI (Metabase) sea el único acceso**: cubre a usuarios no técnicos, pero la adenda exige explícitamente una **API REST programática** para sistemas externos — un dashboard no la reemplaza.
- **Extender la API FastAPI existente** con endpoints nuevos de solo lectura sobre Gold: reusa toda la infra de Fase 1 (auth por API key, rate-limit, métricas, CI/CD) y mantiene un único servicio.

**2. Dónde vive la lógica de negocio / métricas**
- **En la API** (agregaciones y reglas calculadas en Python/SQL ad-hoc dentro de cada endpoint): rápido de escribir, pero lleva a la **"fragmentación de métricas"** — la API y el BI calcularían lo mismo de formas distintas y darían números distintos. Va en contra del principio de *semantic layer*.
- **En Gold / dbt** (la API solo lee; cualquier agregación de negocio se define como vista/modelo en Gold): una única fuente de verdad para las métricas, consumida por igual por la API y el BI. Es el patrón de *semantic layer integrada en el data warehouse*.

**3. Contrato de los endpoints**
- **Reusar el contrato mock de Fase 1** (`/wells` con `id/nombre/lugar/active`) rellenando con datos reales: mantiene el contrato viejo, pero Gold **no tiene** esos campos (`dim_pozo` tiene `idpozo, sigla, cuenca, provincia, formación...`), obligando a **inventar** campos inexistentes — dato no fiel.
- **Endpoints nuevos con el esquema real de Gold**: expone los datos tal como son (*self-describing*), fiel al modelo, dejando el endpoint mock como deprecado por compatibilidad.

**4. Conexión y configuración entre entornos**
- **DSN hardcodeado** en el código: no portable entre entornos y expone credenciales en el repo.
- **DSN por variable de entorno** (`WAREHOUSE_DSN`) con un default solo para desarrollo: portable, sin credenciales productivas en el código, configurable por entorno.

## Decisión

Se implementa la capa de servicio **extendiendo la API FastAPI existente** con endpoints REST de **solo lectura** sobre Gold:

- **Endpoints**: `GET /api/v1/produccion` (sobre `fct_produccion` + dimensiones), `GET /api/v1/pozos` y `GET /api/v1/pozos/{idpozo}` (sobre `dim_pozo`), con sus **campos reales** de Gold. El endpoint mock `/wells` queda **deprecado** (se mantiene por compatibilidad).
- **API como consumidor fino (Data API / headless)**: la lógica de negocio y las agregaciones viven en **Gold/dbt**; la API solo **lee y filtra**. Las consultas son **parametrizadas** (psycopg, placeholders `%(...)s`) → previene inyección SQL.
- **Solo lectura**: únicamente verbos `GET`. Gold es un derivado del pipeline; no se escribe desde la API.
- **Conexión por `WAREHOUSE_DSN`** (variable de entorno) con default solo para desarrollo local; en producción se setea por secret. La **persistencia y ubicación del warehouse en producción** (contenedor co-desplegado vs. base gestionada tipo RDS) es una decisión de la **plataforma de datos**, no de la API — la API es agnóstica a ella vía `WAREHOUSE_DSN`.
- **Reusa** la autenticación por API key y el rate-limiting de Fase 1.

## Consecuencias

**Pros:**
- **Consistencia** con el BI: ambos consumen el mismo Gold → mismos números.
- **Bajo costo de infra**: reusa el servicio, la auth, el rate-limit y el CI/CD de Fase 1.
- **Seguridad**: solo lectura + consultas parametrizadas (sin inyección, verificado con tests de integración) + API key + rate-limit. El error 503 no filtra el DSN.
- **Portabilidad**: misma imagen sirve para local, contenedor y nube; solo cambia `WAREHOUSE_DSN`.
- **Self-describing**: el esquema real se publica vía OpenAPI/Swagger.

**Contras / trade-offs:**
- La API queda **acoplada al esquema de Gold**: un cambio de columnas en Gold puede romper endpoints. Se mitiga con los tests (unitarios + integración) y los modelos Pydantic.
- Las **agregaciones de negocio** requieren crear vistas/modelos en Gold (coordinación con el equipo de datos), en vez de resolverse rápido en la API.

**Dependencia abierta:**
- Definir la **persistencia/ubicación del warehouse en producción** (contenedor co-desplegado en la EC2 vs. base gestionada RDS). Hasta entonces, la API desplegada no tiene un warehouse al que conectarse; el día que exista, solo se setea el secret `WAREHOUSE_DSN`. Esta decisión corresponde a la plataforma de datos y debería documentarse en su propio ADR.
