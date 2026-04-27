# ADR-001: API REST mock con FastAPI y OpenAPI

**Fecha**: 2026-04-27
**Estado**: Aceptado

## Contexto

La Adenda Técnica Fase 1 requiere implementar un mock del servicio API REST para que consumidores externos puedan integrarse antes de que el motor predictivo definitivo esté disponible. La API debe exponer endpoints de consulta de pronóstico y listado de pozos, responder en JSON, validar una API key mediante el header `X-API-Key` y contar con documentación OpenAPI/Swagger accesible en línea.

Además, el mock debe simular la estructura de la API final y devolver datos estáticos o generados con lógica simple.

## Alternativas consideradas

- **Flask**: framework liviano y conocido para APIs HTTP. Permite implementar los endpoints rápidamente, pero requiere agregar extensiones o configuración adicional para validación de parámetros, modelos de respuesta y generación de documentación OpenAPI.

- **Express.js**: framework simple y ampliamente usado en Node.js. Es flexible, pero introduce un stack distinto al resto del proyecto Python y también requiere librerías adicionales para OpenAPI, validación y tipado de contratos.

- **FastAPI**: framework Python orientado a APIs, con validación automática basada en tipos, modelos Pydantic, generación automática de OpenAPI y documentación interactiva en `/docs`. Permite implementar el mock y documentar el contrato de la API con menos configuración adicional.

## Decisión

Se utiliza FastAPI para implementar el mock de la API REST.

La API expone los endpoints bajo el prefijo versionado `/api/v1`:

- `GET /api/v1/forecast`: obtiene el pronóstico de producción de un pozo para un rango de fechas.
- `GET /api/v1/wells`: obtiene el listado de pozos activos.

FastAPI genera automáticamente la especificación OpenAPI y la documentación interactiva de Swagger en `/docs`, cumpliendo el requerimiento de documentación accesible en línea.

La autenticación se implementa mediante una API key preconfigurada en el header `X-API-Key`, con el valor definido por la adenda (`abcdef12345`). Si el header está ausente o tiene un valor incorrecto, la API responde `403 Forbidden`.

El mock utiliza datos estáticos definidos en `app/mock_data.py`. Para `/forecast`, se genera una serie diaria con una tendencia lineal decreciente a partir de una producción base por pozo. Para `/wells`, se devuelven los pozos activos. La respuesta de `/wells` incluye `id_well` y agrega campos descriptivos (`nombre`, `lugar`, `active`) para facilitar la lectura y el monitoreo durante la demo.

Adicionalmente, se aplica rate limiting con `slowapi` usando un límite de `60/minute` sobre los endpoints principales, para evitar abuso accidental del mock y exponer respuestas `429` ante exceso de tráfico.

## Consecuencias

**Pros:**
- OpenAPI y Swagger se generan automáticamente desde el código
- Los modelos Pydantic documentan y validan la estructura de las respuestas
- El versionado `/api/v1` deja espacio para cambios futuros sin romper consumidores
- El mock permite integración temprana sin depender del motor predictivo final
- La lógica de datos simple es suficiente para la Fase 1 y fácil de testear

**Contras:**
- La API key está hardcodeada por tratarse de un mock de Fase 1
- Los datos no provienen de una base persistente ni de un modelo real
- La lógica de pronóstico lineal no representa todavía comportamiento predictivo real
- El rate limiting en memoria es suficiente para una instancia, pero no sería adecuado sin ajustes en un despliegue distribuido
