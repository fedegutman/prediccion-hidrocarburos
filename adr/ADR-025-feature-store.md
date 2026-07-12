# ADR-025: Feature Store (offline + online sobre Gold con dbt)

**Fecha**: 2026-07-10
**Estado**: Aceptado

## Contexto

La Adenda 3 exige (RNF-1) que **el procesamiento y la generación de features quede persistido en un feature store que se use durante la inferencia**. El diagrama de la adenda conecta explícitamente el **Feature Store** con el Servicio de API. Ya tenemos un warehouse Postgres con capa `gold` (esquema estrella) y dbt orquestado por Airflow (Fase 2), así que la decisión es **cómo** materializar y servir las features, no si hace falta un warehouse.

Requisitos concretos del feature store para este proyecto:
- **Persistido** (no calculado al vuelo) y reutilizable por entrenamiento e inferencia.
- **Offline** (histórico, para entrenar) y **online** (última foto por entidad, para predecir).
- **Point-in-time / sin data leakage**: las features de un mes M no pueden usar información de M+1.
- **Multi-target** (petróleo y gas) sobre el mismo grano (`idpozo × mes`).
- **Portable**: sin infra extra ni credenciales de nube (se demuestra en local).

## Alternativas consideradas

**1. Tablas dbt sobre `gold` (elegida).**
- `feat_produccion_offline` (tabla, panel histórico con features + targets `target_*_m1`) y `feat_produccion_online` (tabla, última fila por pozo, sin targets), más un modelo base `feat_produccion_base`.
- Point-in-time garantizado en SQL: lags con `lag()` estrictamente hacia atrás, medias móviles con `rows between N preceding and 1 preceding` (excluyen el mes actual), targets con `lead()`. Tests dbt que lo hacen cumplir (`assert_feat_no_leakage_lag`, `assert_feat_ma_excludes_current`, `assert_feat_target_pointintime`, `assert_feat_online_matches_offline`, `assert_feat_online_freshness`).
- Reusa warehouse + dbt + Airflow existentes; cero infra nueva; corre con `docker compose up`.
- Contra: no es un feature store “con nombre” (no hay API de feature retrieval ni versionado de feature views más allá de `feature_set_version`); el split online/offline es convención nuestra, no un producto.

**2. Feast (feature store dedicado open-source).**
- Da registro de feature views, materialización offline→online y APIs de `get_online_features`.
- Contra: agrega un componente nuevo (registry + online store, típicamente Redis) y una curva de aprendizaje; para 2 fuentes y un grano mensual es sobredimensionado y rompe la portabilidad “un solo docker compose”. No fue visto en clase.

**3. Sin store: calcular features al vuelo en la API / en el training.**
- Menos tablas.
- Contra: **incumple RNF-1** (no queda persistido), duplica la lógica de features entre training e inferencia (training-serving skew) y recomputa ventanas caras en cada request.

**4. Store en un almacén distinto (p. ej. online store en Redis, offline en Parquet/S3).**
- Es el patrón “canónico” de la industria (baja latencia online, batch offline barato).
- Contra: dos tecnologías más + credenciales/infra; el volumen del TP no lo justifica y rompe la portabilidad.

## Decisión

Se implementa el feature store como **modelos dbt materializados en `gold`**:

- `feat_produccion_base` → features derivadas (lags, medias móviles, deltas, ratios) + targets `target_prod_pet_m1` / `target_prod_gas_m1`, todo point-in-time.
- `feat_produccion_offline` (tabla) → panel histórico **con** targets, para **entrenar**.
- `feat_produccion_online` (tabla) → última fila por `idpozo` **sin** targets, para **inferir**.
- La corrección point-in-time se codifica en SQL y se verifica con tests dbt (parte del gate de calidad, ver [ADR-022](ADR-022-gate-calidad-promocion-gold.md)).
- El uso en inferencia es por **scoring batch** (el job de training lee `feat_produccion_online`, predice y persiste en `gold.fct_forecast`, que sirve la API); ver [ADR-026](ADR-026-serving-predicciones.md).

## Consecuencias

**Pros:**
- Cumple RNF-1: features **persistidas** y reutilizadas por training e inferencia, con separación offline/online.
- Point-in-time real y **testeado** (no solo prometido): un test que falle bloquea la promoción de gold.
- Cero infra nueva y portable; reusa el stack de Fase 2 (warehouse + dbt + Airflow).
- El preprocesamiento model-dependent (imputación/one-hot) viaja **con** el modelo (sklearn Pipeline), reduciendo training-serving skew sobre estas features.

**Contras / límites:**
- No hay APIs de feature retrieval ni un registry de feature views como Feast; el contrato online/offline es convención del proyecto.
- El online store es una tabla “última foto”, refrescada por el pipeline batch (no hay online store de baja latencia); suficiente para el horizonte mensual del caso.
- Los nombres de columnas de producción del mes actual son asimétricos por target (`prod_pet_lag0` vs `prod_gas_m`); el consumidor (tracer) debe mapearlos explícitamente.
