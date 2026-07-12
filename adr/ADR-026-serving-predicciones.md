# ADR-026: Serving de predicciones (scoring batch a `gold.fct_forecast`)

**Fecha**: 2026-07-10
**Estado**: Aceptado

## Contexto

La Adenda 3 pide que los **Usuarios de API** consuman una API REST que devuelva las predicciones del modelo, y conecta el **Servicio de API** con el **Feature Store** y el **Model Registry**. Ya existe la API FastAPI (Fase 1/2) y el modelo queda registrado en MLflow con alias `Production` (ver [ADR-024](ADR-024-experiment-tracking-model-registry.md)). La decisión es **cómo** la API entrega predicciones: ¿calcula la inferencia en cada request cargando el modelo, o sirve predicciones precomputadas?

Restricciones del proyecto: el horizonte de predicción es **mensual** (M+1 por pozo), la entrega es **sin servicio live en producción**, y la API en producción corre en una t2.micro con RAM ajustada y sin dependencias de ML pesadas.

## Alternativas consideradas

**1. Scoring batch → tabla `gold.fct_forecast`, la API sirve lo precomputado (elegida).**
- El job de training (Airflow) carga el modelo `@Production` desde MLflow, predice sobre el online store y persiste las predicciones en `gold.fct_forecast` (`idpozo`, `fecha_mes_pred`, `prediccion`, `target_kind`, `model_name`, `model_version`). La API hace un simple `SELECT` filtrando por pozo/target/rango.
- Pros: la API queda **desacoplada** de MLflow, sklearn y del artefacto del modelo (no los importa ni los carga → imagen liviana, sin ML deps en la t2.micro); latencia mínima (una consulta); coherente con el horizonte mensual (no hace falta inferencia en tiempo real); reproducible y auditable (cada fila lleva el `model_version` que la generó).
- Contra: las predicciones son tan frescas como la última corrida del pipeline (no “on-demand” para pozos/fechas arbitrarias); solo sirve el horizonte que el batch materializó.

**2. Inferencia online en la API: cargar el modelo `@Production` y predecir por request.**
- La API leería las features del online store y llamaría al modelo en vivo.
- Contra: mete `mlflow`/`scikit-learn` (y el conflicto de deps con el resto) **dentro** de la API y en la t2.micro; acopla el servicio al artefacto del modelo y a MLflow disponible en runtime; más superficie de fallo por request. Overkill para un forecast mensual que no cambia entre requests.

**3. Servicio de model-serving dedicado (`mlflow models serve`, BentoML, etc.).**
- Endpoint de inferencia gestionado, escalable.
- Contra: otro servicio a desplegar/operar; innecesario para el volumen y el horizonte del TP; rompe la simplicidad “un warehouse + una API”.

## Decisión

Se sirve por **scoring batch precomputado**: el pipeline de training escribe las predicciones en `gold.fct_forecast` (escritura **idempotente por target**: `delete` de las filas del target + `append`, con las tareas de training en serie para que petróleo y gas no se pisen la tabla), y la API expone `GET /api/v1/forecast` que lee esa tabla por `idpozo`, `target` (`prod_pet`/`prod_gas`) y rango de fechas, devolviendo `404` si no hay predicciones y `503` si el warehouse no está disponible.

## Consecuencias

**Pros:**
- Cumple el caso de uso “Usuarios de API consumen predicciones” con una API **liviana y sin dependencias de ML**.
- Multi-target servido correctamente (ambos `target_kind` conviven en la tabla).
- Trazabilidad: cada predicción referencia el `model_version` que la produjo.
- Encaja con la entrega “sin servicio live”: la demo levanta el pipeline en local y la API sirve lo materializado.

**Contras / límites:**
- No hay inferencia on-demand para fechas/pozos fuera de lo que el batch materializó; ampliar el horizonte requiere re-correr el pipeline.
- Frescura ligada a la cadencia del pipeline (`@monthly`); aceptable para un forecast mensual.
- La tabla `fct_forecast` la crea/gestiona el job de ML (no dbt); es una dependencia implícita que el consumidor (API) debe tolerar (por eso el `404` explícito si aún no corrió el pipeline).
