# ADR-016: Tipo de carga de datos (full vs incremental)

**Fecha**: 2026-06-10
**Estado**: Aceptado

## Contexto

La Fase 2 ingiere dos fuentes públicas de datos.gob.ar a la capa Bronze: la **producción mensual de pozos** (granularidad pozo × año × mes) y el **listado maestro de pozos** (un registro por pozo). La adenda pide **definir y justificar explícitamente el tipo de carga** (full / incremental append / merge / upsert), que el procesamiento sea **idempotente** y que sea **posible reprocesar los datos de una fecha**.

Dos hechos del dominio condicionan la decisión:
- La producción **se rectifica retroactivamente** (la fuente trae una columna `rectificado`): un mes ya cargado puede corregirse más adelante.
- Las fuentes **solo se publican como archivo CSV completo**; no hay API ni filtro por fecha del lado del servidor.

## Alternativas consideradas

- **Full load en ambas fuentes** (truncate + reload completo en cada corrida): simple e idempotente. Pero en la producción implica reescribir todas (millones) de filas en cada ejecución aunque solo cambie el último mes, siempre es todo o nada.

- **Incremental append** (solo agregar filas nuevas): eficiente en escritura, pero **incompatible con las rectificaciones**: si un mes viejo se corrige, el append duplicaría el período (la versión vieja y la nueva conviven) en lugar de reemplazarlo. Rompe la idempotencia.

- **Incremental con merge/upsert por período** (borrar e insertar los períodos `(anio, mes)` del rango cargado): idempotente (reejecutar el mismo rango deja el mismo resultado), permite reprocesar un mes específico, y maneja las rectificaciones porque el período corregido pisa al anterior. El costo es la lógica de borrado-por-período antes de insertar.

## Decisión

Se usan **dos estrategias según la naturaleza de cada fuente**:

- **Producción (fact)** → **incremental con merge/upsert por período** `(anio, mes)`. El DAG está parametrizado por rango de fechas (`date_from` / `date_to`); para los períodos del rango, borra esas filas en Bronze y reinserta. Esto da idempotencia, reproceso por fecha y soporte de rectificaciones.

- **Listado de pozos (dimensión maestro)** → **full load** (reemplazo del snapshot). Es un maestro de estado actual, de tamaño chico; el reemplazo completo es lo más simple y correcto, y también es idempotente.

**Limitación asumida**: como la fuente solo entrega el archivo completo, la corrida descarga el CSV entero igual; lo "incremental" ocurre en la **escritura** (qué períodos se upsertan), no en la descarga. Para acotar la lectura en memoria, el CSV se procesa por chunks y se filtra por período antes de cargar.

## Consecuencias

**Pros:**
- Idempotencia en ambas fuentes (reejecutar no duplica ni corrompe)
- Reproceso de un período puntual vía parámetros del DAG (backfill)
- Las rectificaciones de meses pasados se reflejan correctamente
- Memoria acotada al leer por chunks

**Contras:**
- La descarga sigue siendo del archivo completo (no hay incremental real en la lectura)
- El borrado-por-período agrega lógica respecto de un simple append
- El merge asume que `(anio, mes)` define el período a reemplazar. Si la fuente llega a cambiar su granularidad habría que revisar la clave
