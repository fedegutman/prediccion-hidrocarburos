# ADR-031: Manejo de nulos estructurales y cold-start en features

**Fecha**: 2026-07-12
**Estado**: Propuesto

## Contexto

El feature store ([ADR-025](ADR-025-feature-store.md)) se arma sobre un **panel denso**: `feat_produccion_base` cruza cada pozo con los meses contiguos de `dim_tiempo` dentro de su rango observado y hace `LEFT JOIN` con la producción. Esto genera nulos de dos orígenes:

1. **Features de ventana de los primeros meses de cada pozo** (`lag12`, medias móviles de 6/12 meses, etc.): son NULL por construcción porque todavía no hay suficiente historia hacia atrás.
2. **Meses sin reporte** dentro del rango del pozo: el `LEFT JOIN` deja las medidas en NULL (a propósito no se saltean, para que la ventana no se corra).

Hay que decidir qué se hace con esos nulos (imputar vs dropear) y cómo se comporta el sistema ante el **cold-start** en inferencia: un pozo nuevo con poca o ninguna historia. El criterio de referencia (confirmado con cátedra) es entender el **tipo de null** (acá es *not at random*, **estructural**: `lag12 = NULL` no significa 0 producción, es un artefacto inevitable del ventaneo), medir **qué porcentaje** de casos ensucia, elegir el tamaño de ventana en función de eso, considerar si el modelo maneja NaN nativo, y cuidar que cualquier *drop* sea **por entidad**, no aleatorio.

## Alternativas consideradas

**1. Imputar (mediana) y conservar filas; dropear solo filas sin target/baseline (elegida).**
- Los nulos de lags/medias móviles se imputan con `SimpleImputer(strategy="median")` **dentro del `Pipeline` sklearn** (el preprocesamiento viaja con el modelo → mismo tratamiento en train y serve). Solo se dropean las filas sin **label** (último mes por pozo, estructural) y sin **baseline** (`prod_pet_lag0` / `prod_gas_m`).
- Pros: no se descartan las filas de meses tempranos (se conserva información); preprocesamiento **consistente** entre entrenamiento e inferencia; ningún pozo con algo de historia queda sin poder predecir.
- Contra: imputar un `lag12` inexistente con la mediana global inyecta una señal algo **arbitraria** en los meses tempranos; el imputer no distingue "sin dato estructural" de "dato faltante real".

**2. Dropear las filas de meses tempranos sin ventana completa.**
- Empezar el panel de cada pozo recién cuando hay suficiente historia (p. ej. ≥ 12 meses).
- Pros: features siempre completas, sin imputación; se descarta lo más viejo (menos *drift*).
- Contra: se pierden muchas filas (estimado ~30k en un caso análogo); un pozo con menos historia que la ventana quedaría **sin ninguna fila** → agrava el cold-start (el drop pasa a ser **por entidad**).

**3. Modelo con soporte NaN nativo (p. ej. `HistGradientBoostingRegressor`).**
- No imputar; el modelo rutea los NaN internamente.
- Pros: sin imputación arbitraria; maneja tanto el nulo estructural como el faltante real.
- Contra: el estimador actual es `DecisionTreeRegressor` de sklearn, que **no acepta NaN** → obliga a cambiar de familia de modelo (parte de WS5) y ata la decisión de nulos al tipo de modelo.

## Tipos de null y política

- **Estructural (ventaneo)**: no significa 0 producción; artefacto inevitable → **imputado**, no dropeado.
- **Mes sin reporte (`LEFT JOIN`)**: también imputado; el panel denso evita que la ventana se corra.
- **Filas sin target o sin baseline**: **dropeadas** (no aportan al entrenamiento supervisado ni tienen persistencia de referencia).

## Cold-start en inferencia

Un pozo nuevo, con poca o ninguna historia, recibe sus features de ventana **imputadas a la mediana** → el modelo devuelve una predicción de **baja confianza** pero **no falla**. El drop, cuando aplica, es **por entidad / fila estructural**, nunca aleatorio. Como política de robustez se contempla un *fallback*: si el dato del pozo no es **fresco** o falta historia mínima, **degradar al baseline naive** (persistencia M+1 = M) y marcarlo en la respuesta de la API. El online store ya expone `fecha_mes` como *event_time* para chequear freshness/TTL; la degradación en la API todavía no está implementada (ver Consecuencias y [ADR-029](ADR-029-estrategia-horizonte-pronostico.md)).

## Decisión

Imputación por **mediana** dentro del `Pipeline` + **drop** de filas sin target/baseline. Se documenta el nulo como **estructural**. El cold-start se sirve hoy con predicción imputada; el *fallback* a baseline por freshness/falta de historia queda como evolución acordada.

## Consecuencias

**Pros:**
- No se descarta historia; preprocesamiento consistente train/serve (viaja con el modelo).
- Robustez ante pozos nuevos: la inferencia no rompe por features faltantes.

**Contras / límites:**
- La mediana en lags tempranos es una señal débil. **Acción pendiente**: cuantificar el **porcentaje** de filas afectadas y ajustar el tamaño de ventana en función de eso.
- El *fallback* a baseline por freshness está previsto (event_time en el online store) pero **no implementado en la API**. **Acción pendiente**.
- Si se migra a un modelo NaN-aware (WS5), revisar si conviene **dejar de imputar** y delegar los nulos al modelo (alternativa 3).
