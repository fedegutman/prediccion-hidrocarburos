# ADR-019: Estrategia de calidad de datos

**Fecha**: 2026-06-15
**Estado**: Aceptado

## Contexto

La adenda exige **chequeos de calidad persistidos** (no solo asserts en runtime), con **mínimo 3 dimensiones** de las vistas en clase, y que **fallar un check tenga consecuencia operativa** (alerta, bloqueo de promoción aguas abajo, o marca de calidad visible). El pipeline ya transforma con dbt (silver/gold, ver [ADR-015](ADR-015-arquitectura-medallion.md)), así que la estrategia de calidad debe ser coherente con esa herramienta.

## Alternativas consideradas

**Cómo validar:**
- **Solo asserts en runtime** (tests que fallan y se pierden en el log): simple, pero la adenda exige persistencia + consecuencia → no cumple.
- **Great Expectations** (herramienta dedicada de data quality): muy potente (expectations, data docs), pero agrega otra herramienta + infra + dependencias al stack y duplica lo que dbt ya hace sobre los mismos modelos. Sobredimensionado a esta escala.
- **Tests nativos de dbt (schema + singulares) + `store_failures`**: integrados al mismo pipeline que ya construye silver/gold, sin infra extra; las filas que fallan quedan persistidas en tablas.

**Qué consecuencia ante un fallo:**
- **Alerta (Slack):** notifica, pero no impide que el dato malo siga aguas abajo.
- **Bloqueo de promoción aguas abajo:** un test que falla frena que el dato avance (a gold / al deploy). Es la consecuencia más fuerte.
- **Marca de calidad visible:** informa, pero no bloquea.

## Decisión

Calidad con **tests nativos de dbt**, **persistidos** y con **bloqueo** como consecuencia:

- **Tests** en los `_models.yml` (schema: `not_null`, `unique`, `relationships`, `accepted_values`) + **tests singulares** en `tests/` (`assert_*`): grano único de la fact y de producción, no-negatividad de medidas, rango de año válido, integridad referencial fact↔dims, completitud de medidas.
- **Dimensiones cubiertas (≥3):** validez (rango / `accepted_values`), unicidad/grano, integridad referencial, completitud y schema/tipado.
- **Persistencia:** `+store_failures: true` con `+schema: dq_failures` → cada test que falla deja **sus filas en una tabla** del schema `dq_failures` (auditable, no se pierde en el log).
- **Consecuencia = bloqueo de promoción:** el job `dbt-tests` del CI corre `dbt build` (run + test) y, al estar en `needs` de `build-and-scan`, **un test de calidad roto bloquea el build y el deploy** → el dato malo no llega a producción.

## Consecuencias

**Pros:**
- Una sola herramienta (dbt) para transformar y validar; sin infra de DQ extra.
- Fallos **persistidos y auditables** en `dq_failures`.
- Consecuencia real: el dato roto **no se promueve** (gate en CI).
- Cubre holgadamente las ≥3 dimensiones pedidas.

**Contras / límites:**
- `store_failures` **sobreescribe** la tabla en cada corrida → no hay histórico de DQ salvo que se versione aparte.
- Hoy el gate vive en **CI** (sobre un fixture chico). Falta replicar el bloqueo **dentro del DAG** (frenar la promoción a gold en la corrida real con datos reales, antes de exponerlos) — pendiente en la orquestación.
