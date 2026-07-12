# ADR-030: Ubicación del target en el feature store (label en el offline, online sin label)

**Fecha**: 2026-07-12
**Estado**: Propuesto

## Contexto

El feature store ([ADR-025](ADR-025-feature-store.md)) tiene una capa **offline** (histórico, para entrenar) y una **online** (última foto por pozo, para inferir). Queda una decisión puntual: ¿el **label** (`target_prod_pet_m1` / `target_prod_gas_m1`) vive **dentro** de la tabla del feature store, o se genera aparte en el pipeline de entrenamiento?

El criterio de referencia (confirmado con cátedra) es que un feature store *idealmente* contiene **solo features**, con tres riesgos si el label va junto: (a) el feature store es una **capa compartida** que puede servir a varios modelos/usos; (b) el store alimenta también la **inferencia online**, donde el target no existe (es justo lo que se predice); (c) tener features y label juntos es un **riesgo de data leakage**.

## Alternativas consideradas

**1. Target en el offline store; online sin target (elegida).**
- `feat_produccion_offline` (tabla) materializa las features **más** los labels `target_*_m1` (point-in-time, `lead(+1)`); `feat_produccion_online` se construye **sobre** el offline pero **excluye** los labels (comentario explícito en el modelo: "SIN target").
- Pros: una **única fuente de verdad** de features (offline y online comparten exactamente la misma transformación → sin training-serving skew); el label point-in-time se calcula una sola vez en dbt (donde ya está el panel denso contiguo) y queda **testeado**; el path de inferencia queda sin target por construcción.
- Contra: la tabla offline **mezcla** features y label (no es "features puras"); un consumidor descuidado podría usar el target como feature si no lo excluye a mano.

**2. Feature store solo con features; target generado en el pipeline de training.**
- El training toma las features del store y calcula el label con un shift temporal propio (SQL/Python).
- Pros: store "puro" (patrón canónico), reutilizable por cualquier modelo/uso sin arrastrar labels; imposible filtrar el label desde el store.
- Contra: **mueve la lógica del label fuera del store**, donde ya está el panel denso point-in-time; si el panel del training no es contiguo, el shift `M+1` puede calcularse mal (el motivo por el que el label se calcula en dbt); más acople entre el training y la definición del label.

**3. Tabla de labels separada, unida en training.**
- Una tabla `labels(idpozo, fecha_mes, target_*)` aparte, joineada a las features al entrenar.
- Pros: separa limpiamente features de labels; el store queda puro y el label se versiona por separado.
- Contra: una tabla más a mantener y joinear; para un único grano/label mensual es *overhead*.

## Cómo se mitigan los tres riesgos

- **(b) online sin target**: `feat_produccion_online` no lleva labels; la inferencia nunca ve el target.
- **(c) leakage**: el target es point-in-time (`lead(+1)`) y el training **excluye explícitamente** ambos targets del set de features (constante `NON_FEATURES` en `tracer_bullet.py`); hay tests dbt que lo hacen cumplir (`assert_feat_target_pointintime`, `assert_feat_online_matches_offline`).
- **(a) capa compartida**: el multi-target (petróleo + gas) ya comparte el mismo store; sumar otros modelos solo requiere que ignoren las columnas `target_*` (igual que hoy).

## Decisión

Se mantiene el **label en el offline store** (`feat_produccion_offline`), el **online sin label** (`feat_produccion_online`), y el training **excluye** los targets del set de features. El label se calcula point-in-time en dbt y se valida con tests (parte del gate de calidad de datos, ver [ADR-022](ADR-022-gate-calidad-promocion-gold.md)).

## Consecuencias

**Pros:**
- Single source of truth de features; label point-in-time calculado y **testeado** una sola vez; path de inferencia limpio (online sin target).
- Cero infra extra; se resuelve dentro del stack dbt existente.

**Contras / límites:**
- La tabla offline no es "features puras": el consumidor **DEBE** excluir los targets explícitamente (hoy lo hace `NON_FEATURES`); si esa exclusión se rompe, hay leakage.
- Si a futuro el store se comparte con muchos modelos con labels distintos, conviene migrar a la **alternativa 3** (tabla de labels separada) para no acoplar labels al store.
