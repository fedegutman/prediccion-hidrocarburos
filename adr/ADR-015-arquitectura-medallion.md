# ADR-015: Arquitectura medallion (Bronze / Silver / Gold)

**Fecha**: 2026-06-09
**Estado**: Aceptado

## Contexto

La Fase 2 requiere procesar datos públicos de producción de hidrocarburos desde su forma cruda (CSVs de datos.gob.ar) hasta un modelo listo para consumo de negocio. La adenda exige explícitamente **utilizar la arquitectura medallion** para procesar los datos, que el procesamiento sea **idempotente** y **reprocesable por fecha**, y que existan **chequeos de calidad** entre etapas. Necesitamos una forma de organizar las transformaciones que permita auditar dónde se rompe un dato y reprocesar sin volver a la fuente.

## Alternativas consideradas

- **Transformación monolítica (una sola capa de staging + tablas finales)**: separar solo "datos crudos" de "datos finales". Deja en un mismo paso la limpieza/tipado y el modelado dimensional, lo que dificulta aislar problemas de calidad de datos de probleamas de modelado, y reduce los puntos donde insertar chequeos.

- **Arquitectura medallion (Bronze -> Silver -> Gold)**: tres capas con responsabilidades separadas. Bronze guarda el dato crudo inmutable (permite reprocesar sin re-descargar); Silver limpia, tipa y deduplica; Gold expone el modelo estrella. Cada frontera entre capas es un punto natural para chequeos de calidad y para garantizar idempotencia por partición de fecha. Es además la arquitectura exigida por la adenda.

## Decisión

Se adopta la **arquitectura medallion** con tres schemas en el warehouse Postgres: `bronze`, `silver` y `gold`. La extracción (Airflow) aterriza el dato crudo en `bronze`; dbt construye `silver` (limpieza/tipado/dedup) y `gold` (modelo estrella). Los chequeos de calidad se ubican en las fronteras entre capas, y la idempotencia se implementa reescribiendo por partición de fecha, lo que habilita el reprocesamiento histórico.

## Consecuencias

**Pros:**
- Responsabilidades separadas: si un dato sale mal, se identifica en qué capa
- Bronze inmutable: se puede reprocesar Silver/Gold sin volver a descargar la fuente
- Cada frontera entre capas es un punto natural para chequeos de calidad
- Facilita la idempotencia y el reprocesamiento por fecha

**Contras:**
- Más tablas y almacenamiento que una carga directa (el mismo dato vive en varias capas)
- Mayor cantidad de objetos a mantener y orquestar
- Para volúmenes muy chicos puede parecer un tanto overkill, pero se justifica por la auditabilidad y el reproceso exigidos
