{% docs __overview__ %}

# Catálogo de Datos — OilGas

Catálogo y linaje de la **plataforma de datos de hidrocarburos** (Trabajo Integrador, Ingeniería de Software 2026). Esta es la portada del catálogo dbt; el **punto de entrada único de gobierno** (que enmarca también Airflow, Metabase y la salud de calidad) es el [portal de gobierno](../index.html) (en el sitio publicado, un nivel arriba de este catálogo).

## Arquitectura medallion

| Capa | Schema | Qué es |
|------|--------|--------|
| **Bronze** | `bronze` | Dato crudo de las 2 fuentes de datos.gob.ar (producción + maestro de pozos), con metadata técnica de carga por registro (`_ingestion_ts`, `_source_url`, `_batch_id`, …, ver ADR-023). |
| **Silver** | `silver` | Limpio, tipado y deduplicado — modelos `stg_*` (vistas). |
| **Gold** | `gold` | Modelo estrella `fct_produccion` + `dim_pozo/empresa/area/tiempo` (ADR-017). Consumido por la API y el BI. |

## Cómo navegar este catálogo

- **Lineage**: el grafo Bronze → Silver → Gold está en el ícono inferior derecho (o en cada modelo, pestaña *Lineage Graph*).
- **Modelos y columnas**: el panel izquierdo lista los modelos por proyecto; cada uno tiene descripción, columnas, tests y `meta` (owner/dominio).
- **Tests de calidad**: cada modelo muestra sus tests; las filas que fallan se persisten en el schema `dq_failures` (ADR-019).

## Gobierno

- **Catálogo / linaje** → este sitio (dbt docs).
- **Workflows + última actualización** → Airflow.
- **BI** → Metabase (dashboard "Producción de Hidrocarburos").
- **Decisión de gobierno** (dbt docs + Airflow, sin DataHub) → ADR-020.

{% enddocs %}
