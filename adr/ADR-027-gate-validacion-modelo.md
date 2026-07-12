# ADR-027: Gate de validación del modelo antes de promover a Production

**Fecha**: 2026-07-10
**Estado**: Aceptado

## Contexto

El diagrama de la Adenda 3 incluye un bloque **Validation** entre Training y el Model Registry, y pide que el entrenamiento/despliegue sea recurrente y automático (RNF). Sin un control, el pipeline promovería a `Production` **cualquier** modelo entrenado, incluso uno peor que un baseline trivial — y como la API sirve lo que apunta el alias `Production` (ver [ADR-026](ADR-026-serving-predicciones.md)), un modelo malo llegaría directo a los usuarios. Hace falta una compuerta de calidad del **modelo** (análoga al gate de calidad de **datos** de [ADR-022](ADR-022-gate-calidad-promocion-gold.md)).

El modelo actual es un *tracer bullet* deliberadamente trivial (`DecisionTreeRegressor(max_depth=4)`); todavía **no supera** al baseline naive (predecir M+1 = M): su `skill = 1 - mae/mae_baseline` es levemente negativo. Es decir, el gate no puede exigir hoy `skill >= 0` sin bloquear toda promoción.

## Alternativas consideradas

**1. Gate por umbral de skill configurable, con default leniente y promoción condicional (elegida).**
- Se calcula `skill` sobre un split **temporal** de validación (los meses más recientes) y se promueve a `Production` solo si `skill >= MIN_SKILL`. `MIN_SKILL` es una env var; default `-1.0` (rechaza solo modelos catastróficos, >2× peores que el baseline) mientras el modelo sea el tracer bullet, y se sube a `0.0` cuando aterrice el modelo real.
- Todo candidato se **registra** igual en MLflow (queda trackeado) con un tag `validation_passed`; solo el alias `Production` es condicional. Si no pasa, se mantiene el `Production` anterior (*last-good*) y el task falla (visible en Airflow) — nunca se sirve un modelo no validado.
- Pros: mecanismo real y demostrable (bajando/subiendo el umbral se ve promover vs rechazar); no bloquea la demo del tracer bullet; separa “registrar” (siempre) de “promover” (condicional).
- Contra: el umbral default es laxo por ahora (es explícito y documentado, no un descuido).

**2. Gate por regresión contra el `Production` actual (promover solo si mejora al incumbente).**
- Evita umbrales absolutos.
- Contra: requiere cargar y re-evaluar el modelo incumbente en cada corrida (más código y acople); en el primer run no hay incumbente (hay que bootstrapear igual). Se puede adoptar cuando haya un modelo real estable.

**3. Sin gate: promover siempre (estado previo).**
- Más simple.
- Contra: incumple el espíritu del bloque *Validation*; un modelo peor que el baseline llega a la API. Es justamente lo que este ADR corrige.

**4. Validación manual (un humano aprueba en la UI de MLflow antes de mover el alias).**
- Control total.
- Contra: rompe “recurrente y automático” (RNF); no escala ni es reproducible en un pipeline desatendido.

## Decisión

Se agrega un **gate de validación automático** en `tracer_bullet.py`:

1. Entrenar y evaluar en split temporal → `mae`, `rmse`, `mae_baseline`, `skill`.
2. Loguear params/métricas en MLflow y `registrar` la versión del modelo (siempre), con tag `validation_passed`.
3. **Promover a `Production` y reescribir `gold.fct_forecast` solo si `skill >= MIN_SKILL`.** Si no, se conserva el `Production` anterior, no se tocan las predicciones y el task falla.

`MIN_SKILL` default `-1.0` (tracer bullet); objetivo `0.0` con el modelo real.

## Consecuencias

**Pros:**
- Materializa el bloque **Validation** de la adenda: ningún modelo llega a la API sin pasar la compuerta.
- Configurable y demostrable en el video (mismo modelo, distinto `MIN_SKILL` → promueve o rechaza).
- Registra todos los candidatos (trazabilidad) pero desacopla el registro de la promoción.
- Complementa el gate de **datos** (ADR-022): datos validados en gold + modelo validado antes de servir.

**Contras / límites:**
- El umbral default es intencionalmente laxo mientras el estimador sea trivial; hay que **subirlo a 0.0** al integrar el modelo real, o el gate aporta poco.
- Compara contra un baseline naive, no contra el modelo en producción (ver alternativa 2 como evolución).
- Si el gate rechaza y no existe un `Production` previo, no hay predicciones que servir hasta que un modelo pase (comportamiento correcto, pero a tener en cuenta en entornos nuevos con umbral estricto).
