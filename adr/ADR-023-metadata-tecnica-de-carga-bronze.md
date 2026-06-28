# ADR-023: Metadata técnica de carga por registro en Bronze

**Fecha**: 2026-06-28
**Estado**: Aceptado

## Contexto

La capa Bronze ([ADR-016](ADR-016-tipo-de-carga.md)) aterriza las dos fuentes de datos.gob.ar tal cual, con `to_sql`. Las tablas `bronze.pozos` y `bronze.produccion` quedaban con **solo columnas de negocio**: mirando una fila en SQL no se podía saber **cuándo** se ingirió, **de qué corrida** (DAG run) salió, **de qué URL/archivo** vino, ni detectar si el archivo origen cambió entre corridas. La única trazabilidad vivía **fuera del dato** (el `run_id` en los logs de Airflow), no consultable junto a las filas.

Esto es una observación explícita de la corrección de la cátedra ("a Bronze le falta metadata técnica de carga por registro") y es coherente con el espíritu de [ADR-016](ADR-016-tipo-de-carga.md) (reproceso por período: saber qué corrida dejó cada fila) y de [ADR-020](ADR-020-gobierno-de-datos.md) (gobierno: "última vez que se actualizó"). Además, en la Fase 3 el **linaje de cada feature** se apoya en saber qué corrida produjo cada registro.

## Alternativas consideradas

**Dónde guardar la metadata de carga:**
- **Columnas técnicas en la propia tabla Bronze (elegida):** la trazabilidad viaja con el dato, consultable en el mismo `SELECT`. Denormalizado (mismo valor repetido por fila de la corrida), pero trivial de consultar y auditar.
- **Tabla de auditoría separada (`bronze.ingestion_log`) referenciada por `_batch_id`:** normalizado (un registro por corrida), pero exige un JOIN para responder "cuándo/de dónde vino esta fila" y agrega una tabla y su mantenimiento. Sobredimensionado a esta escala.
- **Solo en Airflow/logs (status quo):** no cumple la corrección; la metadata no es consultable junto al dato.

**Cómo agregar las columnas a tablas que ya existen** (la fuente del problema: `to_sql(append)` NO agrega columnas nuevas a una tabla preexistente):
- **`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` idempotente dentro de la carga (elegida):** el warehouse existente se auto-migra en la próxima ingesta, sin script manual. En tabla nueva, `to_sql` ya la crea con las columnas.
- **Script de migración manual una sola vez:** un paso extra fuera del pipeline, fácil de olvidar y de desincronizar entre ambientes.
- **Recrear la tabla (DROP + CREATE):** rompería la vista dependiente `silver.stg_pozos` (mismo motivo por el que la carga full usa TRUNCATE y no DROP, ver bronze_lib).

## Decisión

Se agregan **6 columnas técnicas** (prefijo `_` para distinguirlas del negocio) a ambas tablas Bronze, enriqueciendo el DataFrame en pandas **justo antes de cada `to_sql`** (`_with_metadata` en `bronze_lib.py`):

| Columna | Contenido |
|---|---|
| `_ingestion_ts` | timestamp UTC de la ingesta |
| `_source_url` | URL de datos.gob.ar de origen |
| `_source_file` | nombre del archivo CSV |
| `_batch_id` | `run_id` del DAG de Airflow |
| `_load_type` | `'full'` (pozos) / `'merge'` (producción) |
| `_file_md5` | hash MD5 del CSV descargado |

- El DAG `bronze_ingesta` propaga `run_id` y la URL a las dos tareas de carga (`load_pozos` ahora recibe `**context`).
- Las tablas preexistentes se auto-migran con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (helper `_ensure_meta_cols`) antes del append.
- **NO se propaga a Silver**: `stg_*` selecciona por nombre explícito y `_sources.yml` no fija la lista de columnas, así que las columnas `_` se ignoran solas y el contrato Bronze→Silver no cambia.

## Consecuencias

**Pros:**
- Trazabilidad/auditoría **por registro, consultable en SQL** (cuándo, de qué corrida, de qué archivo/URL, con qué hash).
- Base para el **linaje de features** de Fase 3 (qué corrida produjo cada dato).
- Cambio **aditivo y de bajo riesgo**: no toca Silver/Gold ni los fixtures de CI; el warehouse existente se auto-migra.
- `_file_md5` permite detectar si la fuente cambió entre corridas.

**Contras / límites:**
- Metadata **denormalizada**: el mismo valor se repite en cada fila de la corrida (costo de storage menor; se aceptó por simplicidad de consulta).
- En el overwrite por período (merge) o full, reprocesar **pisa** el `_ingestion_ts`/`_batch_id` anterior de esas filas → no hay histórico de cargas a nivel fila (consistente con el modelo SCD1/overwrite de Bronze; el histórico de corridas, si se quisiera, iría en la tabla de auditoría descartada).
