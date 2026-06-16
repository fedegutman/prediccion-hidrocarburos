# Runbook — Data/Analytics Engineer: Reprocesamiento histórico (backfill)

**Rol:** Data/Analytics Engineer (perfil de implementación).
**Última actualización:** 2026-06-15.

## Propósito y disparador
Reprocesar la producción de uno o más **períodos pasados** cuando la fuente
(datos.gob.ar) **corrige o completa** datos ya cargados (ej. una operadora rectifica
la producción de un mes), de modo que el warehouse (`gold`) refleje el dato corregido
**sin duplicar ni romper** la cadena bronze→silver→gold.

**Disparador:** pedido del equipo de datos, detección de discrepancia entre la fuente
y `gold`, o aviso de rectificación en la fuente. No es programado: se corre **a demanda**.

## Rol/dueño y prerrequisitos
- **Quién lo corre:** el Data Engineer de guardia.
- **Accesos/insumos:** acceso al host donde corre `data_platform` (Airflow), credenciales del warehouse, y el **período a reprocesar** (`anio`/`mes` o rango de fechas).
- **Herramientas:** Airflow (DAG `bronze_ingesta`), dbt (proyecto `oilgas`).

## Pasos
1. **Identificar el período** (ej. `2024-03`) y confirmar con la fuente que el dato corregido ya está publicado.
2. **Re-ingestar Bronze** del período: disparar el DAG `bronze_ingesta` con los parámetros de fecha (`date_from`/`date_to`). La carga es **idempotente** (ver Decisión funcional): producción se carga con TRUNCATE+append del rango y el maestro de pozos con full TRUNCATE+append → correrlo N veces deja el mismo resultado, sin duplicados.
3. **Reconstruir Silver/Gold:** `dbt build` (o `dbt build --select silver+ gold+`) → reconstruye los modelos y **corre los tests de calidad**.
4. **Revisar la consecuencia de calidad:** si algún test falla, la promoción queda frenada (ver [ADR-019](../../adr/ADR-019-calidad-de-datos.md)). Inspeccionar las filas persistidas en el schema `dq_failures`.

## Validación
- `dbt build` termina con **PASS, sin ERROR**.
- Query de control (totales del período vs. la fuente):
  ```sql
  SELECT anio, mes, SUM(prod_pet), SUM(prod_gas)
  FROM gold.fct_produccion WHERE anio=2024 AND mes=3 GROUP BY 1,2;
  ```
- **Grano único** (sin duplicados): lo cubre `assert_produccion_grano_unico`.
- Spot-check vía API: `GET /api/v1/produccion?anio=2024` devuelve los valores corregidos.

## Si algo falla
- **Tests de calidad en rojo:** NO promover. Revisar `dq_failures`, corregir la transformación o el dato de origen, y re-correr. El gate (CI / DAG) impide que el dato malo avance.
- **Carga a medias / error de conexión:** la idempotencia permite **re-correr** sin efectos colaterales (no se duplica).
- **Necesidad de volver atrás:** Bronze se reconstruye desde la fuente y Silver/Gold son derivados de dbt → el "rollback" es re-correr la ingesta con el dato anterior, o restaurar el backup del warehouse.
- **Escalamiento:** si la discrepancia persiste, escalar al owner de la plataforma de datos.

## Consideraciones no funcionales
- **Frescura:** el backfill debe dejar `gold` consistente con la fuente para el período.
- **Idempotencia/calidad:** re-correr no debe duplicar ni degradar (garantizado por la carga + los tests).
- **Costo:** reprocesar **solo el rango afectado**, no todo el histórico, para no recomputar de más.
- **Seguridad/privacidad:** sin PII (datos públicos de datos.gob.ar).

## Decisiones explícitas (justificadas)
**Funcional — carga TRUNCATE+append (no DROP, no INSERT incremental ciego):**
Se eligió TRUNCATE+append porque hace el reproceso **idempotente** y **no rompe las vistas dependientes** (`silver.stg_*`), a diferencia de DROP. Desde la perspectiva del engineer, esto es exactamente lo que vuelve a un backfill **seguro de repetir** ante fallos: puedo re-correr el período sin miedo a duplicar ni a romper bronze→silver→gold. (Ver [ADR-016](../../adr/ADR-016-tipo-de-carga.md).)

**No funcional — no promover a gold si fallan los tests (umbral de calidad = 0 errores):**
Se decide que un backfill con tests en rojo **NO se promueve**. Desde los incentivos del engineer, prefiero **frenar y arreglar** antes que propagar dato corregido-pero-inconsistente a quienes consumen `gold` (API, BI): un número malo en producción cuesta más (decisiones erradas + pérdida de confianza) que demorar el reproceso.
