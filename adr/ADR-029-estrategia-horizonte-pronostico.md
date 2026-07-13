# ADR-029: Estrategia de horizonte de pronóstico (single-step M+1 con cap)

**Fecha**: 2026-07-12
**Estado**: Aceptado

## Contexto

La API `GET /api/v1/forecast` acepta un rango de fechas arbitrario (`date_start`..`date_end`), pero el modelo se entrena para predecir **un solo paso hacia adelante (M+1)**: el label es `target_{target}_m1` (= `lead(prod, 1)` sobre el panel denso, ver [ADR-025](ADR-025-feature-store.md)) y el scoring batch materializa **una fila por pozo** en `gold.fct_forecast` (el mes siguiente al último dato observado). Para rangos que caen fuera de ese mes, la API responde `404`.

El problema es clásico de forecasting: pronosticar a horizontes más lejanos requiere las features de ventana (lags, medias móviles) de los meses intermedios, que **todavía no existen**. Hay que decidir explícitamente **cómo** se cubre un horizonte mayor a un mes, porque hoy el contrato de la API (rango arbitrario) está sobre-especificado respecto de lo que el modelo entrega (solo M+1). Las features de ventana son las que más aportan sobre el baseline, así que descartarlas a horizonte lejano degrada el modelo, pero construirlas propagando predicciones propaga error.

## Alternativas consideradas

**1. Single-step M+1 con cap de horizonte (elegida).**
- El modelo predice únicamente el mes siguiente; el horizonte servible se limita a lo que el batch materializa (M+1). La API acota el rango y comunica el límite (en vez de devolver un pronóstico inventado para meses no cubiertos).
- Pros: simple y sin propagación de error; coherente con el grano mensual y con el serving batch ([ADR-026](ADR-026-serving-predicciones.md)); baseline honesto para el *tracer bullet* actual (el modelo real es WS5); las features de ventana están completas (solo se usan datos hasta M).
- Contra: no cubre horizontes lejanos; el contrato de rango de la API queda acotado a un mes hasta que aterrice una estrategia multi-step.

**2. Autoregresivo / recursivo multi-step.**
- Predecir M+1, realimentar esa predicción para construir las features de ventana de M+2, y así sucesivamente hasta el horizonte pedido.
- Pros: un único modelo cubre cualquier horizonte; conserva las features de ventana (las más informativas).
- Contra: **propaga el error** del modelo a horizontes lejanos; requiere cálculo **secuencial on-the-fly** (más latencia/recursos); las features autorregresivas ya no salen tal cual del online store: las estáticas (pozo, profundidad, cuenca) sí, pero las dependientes de pasos previos deben calcularse en vivo (criterio confirmado con cátedra).

**3. Directo: un modelo por horizonte (h = 1..H).**
- Entrenar un modelo distinto por cada horizonte objetivo.
- Pros: sin propagación de error; cada horizonte se optimiza por separado.
- Contra: `H` modelos a entrenar, registrar, versionar y servir (explosión de artefactos en el registry); `H` fijo y acotado de antemano.

**4. Modelo tolerante a NaN (ventanas no disponibles como nulos).**
- Usar un estimador que maneje NaN nativo (p. ej. `HistGradientBoostingRegressor`) y tratar como nulas las features de ventana no disponibles a horizonte lejano.
- Pros: un solo modelo, sin recursión.
- Contra: a horizonte lejano casi todas las features de ventana son nulas → el modelo degrada a poco más que las estáticas, con poco poder predictivo; solo aplica si se cambia de familia de modelo (ver [ADR-031](ADR-031-nulos-estructurales-cold-start.md)).

A nivel **sistema**, en las cuatro opciones aplica un **cap de horizonte máximo** (recomendado por cátedra) y la posibilidad de una estrategia primaria con *fallback* a una segunda, reportando la estrategia usada en la respuesta de la API.

## Decisión

- El horizonte servible es **M+1 (single-step)**, materializado por scoring batch en `gold.fct_forecast`.
- Se **acota el rango de la API** al horizonte materializado. Para pedidos fuera de rango, la respuesta DEBE reflejar explícitamente el límite del horizonte (mensaje claro / metadato de horizonte) en lugar de un pronóstico no soportado.
- Como *fallback* ante ausencia de predicción fresca, se contempla degradar al **baseline naive de persistencia** (M+1 = M), marcándolo en la respuesta (se coordina con el cold-start de [ADR-031](ADR-031-nulos-estructurales-cold-start.md)).
- La evolución prevista, al integrar el modelo real (WS5), es **directo (opción 3) o autorregresivo (opción 2) con cap**, elegido según el error observado por horizonte y el costo de cómputo.

## Consecuencias

**Pros:**
- Decisión honesta y simple; sin propagación de error; alineada con el serving batch y el grano mensual del caso.
- Deja escrito el camino de evolución (directo/autorregresivo) para cuando el modelo justifique horizontes mayores.

**Contras / límites:**
- El contrato de la API acepta rangos multi-mes pero solo hay M+1 disponible. **Acción pendiente**: acotar/documentar el horizonte en OpenAPI y devolver un mensaje explícito en vez de un `404` seco.
- No hay pronóstico a varios meses hasta implementar la opción 2 o 3.
- El *fallback* a baseline por freshness todavía no está implementado en la API (ver [ADR-031](ADR-031-nulos-estructurales-cold-start.md)).
