"""Tracer bullet de la Fase 3: circuito ML end-to-end con un modelo trivial.

Lee el feature store (solo features, sin target) -> genera el target dinámicamente
con shift temporal -> entrena un modelo simple -> lo loguea y registra en MLflow ->
predice sobre el online store y escribe gold.fct_forecast.

El objetivo es validar que las piezas se conectan (feature store <-> MLflow <-> inferencia),
NO la precisión: el modelo real, la validación walk-forward y el tuning son WS5.

Configurable por env vars (defaults = docker-compose):
  WAREHOUSE_DSN, MLFLOW_TRACKING_URI, TARGET ('prod_pet' o 'prod_gas').
"""

import os

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeRegressor
from sqlalchemy import create_engine

WAREHOUSE_DSN = os.getenv("WAREHOUSE_DSN", "postgresql://dwh:dwh@warehouse:5432/oilgas")
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
TARGET = os.getenv("TARGET", "prod_pet")

# lag0 es la producción del mes actual — el baseline naive es predecir M+1 = M
BASELINE_COL = f"{TARGET}_lag0"
MODEL_NAME = f"forecast_{TARGET}"

# columnas que NO son features: índices y metadata
NON_FEATURES = {
    "pozo_sk", "idpozo", "tiempo_sk", "fecha_mes",
    "feature_set_version",
}


def build_pipeline(num_cols, cat_cols):
    """Pipeline = preprocesamiento (la 'feature view' model-dependent) + estimador.

    El one-hot/imputación viajan CON el modelo, así inferencia usa el mismo preprocesamiento
    que el entrenamiento (anti training-serving skew).
    """
    pre = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ])
    # estimador trivial a propósito; el modelo real es WS5
    return Pipeline([("pre", pre), ("model", DecisionTreeRegressor(max_depth=4, random_state=0))])


def generate_target(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Genera el target dinámicamente: M+1 = producción del mes siguiente.

    El target NO vive en el feature store (riesgo de data leakage y no disponible
    en inferencia online). Se genera haciendo un shift(-1) temporal por pozo.

    Filas sin target (último mes de cada pozo) se dropean — son nulos estructurales
    inevitables del ventaneo, no pérdida de información real (ver ADR-025).
    """
    df = df.sort_values(["idpozo", "fecha_mes"]).copy()
    df["_target"] = df.groupby("idpozo")[target_col].shift(-1)
    # dropear filas sin target (último mes por pozo no tiene M+1)
    df = df[df["_target"].notna()].copy()
    return df


def main():
    engine = create_engine(WAREHOUSE_DSN)

    # --- leer SOLO features del feature store (sin target) ---
    df = pd.read_sql("select * from gold.feat_produccion_offline", engine)

    if df.empty:
        raise SystemExit("Feature store vacío (¿corriste el pipeline de datos?).")

    # --- generar target dinámicamente en el pipeline de entrenamiento ---
    df = generate_target(df, TARGET)

    # filas válidas: tienen baseline (producción del mes actual reportada)
    df = df[df[BASELINE_COL].notna()].copy()

    if df.empty:
        raise SystemExit("Sin filas de entrenamiento válidas tras generar el target.")

    feat_cols = [c for c in df.columns if c not in NON_FEATURES and c != "_target"]
    cat_cols = [c for c in feat_cols if df[c].dtype == object]
    num_cols = [c for c in feat_cols if c not in cat_cols]

    # --- split TEMPORAL (no aleatorio): validación = el 20% de meses más recientes ---
    corte = df["fecha_mes"].quantile(0.8)
    tr = df[df["fecha_mes"] <= corte]
    va = df[df["fecha_mes"] > corte]
    if va.empty:
        tr = va = df

    pipe = build_pipeline(num_cols, cat_cols)
    pipe.fit(tr[feat_cols], tr["_target"])
    pred = pipe.predict(va[feat_cols])

    mae = mean_absolute_error(va["_target"], pred)
    rmse = root_mean_squared_error(va["_target"], pred)
    mae_base = mean_absolute_error(va["_target"], va[BASELINE_COL])
    skill = 1 - mae / mae_base if mae_base else 0.0

    # --- MLflow: tracking + registry ---
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("oilgas-forecast")
    with mlflow.start_run(run_name=f"tracer-{TARGET}") as run:
        mlflow.log_params({
            "target": TARGET,
            "modelo": "DecisionTree(max_depth=4)",
            "n_train": len(tr),
            "n_valid": len(va),
            "n_features": len(feat_cols),
            "target_generacion": "shift(-1) por pozo en pipeline (no en feature store)",
        })
        mlflow.log_metrics({
            "mae": mae,
            "rmse": rmse,
            "mae_baseline": mae_base,
            "skill_score": skill,
        })
        mlflow.sklearn.log_model(
            pipe,
            artifact_path="model",
            signature=infer_signature(va[feat_cols], pred),
        )
        run_id = run.info.run_id

    # registrar la versión y marcarla Production
    client = MlflowClient(tracking_uri=TRACKING_URI)
    version = mlflow.register_model(f"runs:/{run_id}/model", MODEL_NAME).version
    client.set_registered_model_alias(MODEL_NAME, "Production", version)

    # --- inferencia: predecir M+1 desde el online store y escribir gold.fct_forecast ---
    model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@Production")
    online = pd.read_sql("select * from gold.feat_produccion_online", engine)
    online["prediccion"] = model.predict(online[feat_cols])

    out = online[["idpozo", "fecha_mes", "prediccion"]].rename(
        columns={"fecha_mes": "fecha_mes_base"}
    )
    out["fecha_mes_pred"] = (
        pd.to_datetime(out["fecha_mes_base"]) + pd.DateOffset(months=1)
    ).dt.date
    out["target_kind"] = TARGET
    out["model_name"] = MODEL_NAME
    out["model_version"] = version
    out.to_sql("fct_forecast", engine, schema="gold", if_exists="replace", index=False)

    print(
        f"[tracer] target={TARGET} | MAE={mae:.1f} baseline={mae_base:.1f} "
        f"skill={skill:.3f} | modelo {MODEL_NAME} v{version} -> Production "
        f"| {len(out)} forecasts en gold.fct_forecast"
    )


if __name__ == "__main__":
    main()