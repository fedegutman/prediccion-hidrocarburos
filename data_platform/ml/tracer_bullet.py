"""Tracer bullet de la Fase 3: circuito ML end-to-end con un modelo trivial.

Lee el feature store -> entrena un modelo simple -> lo loguea y registra en MLflow ->
predice sobre el online store y escribe gold.fct_forecast. El objetivo es validar que las
piezas se conectan (feature store <-> MLflow <-> inferencia), NO la precisión: el modelo
real, la validación walk-forward y el tuning son WS5.

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
TARGET = os.getenv("TARGET", "prod_pet")  # 'prod_pet' o 'prod_gas' (multi-target del feature store)

TARGET_COL = f"target_{TARGET}_m1"
# baseline naive de persistencia: predecir M+1 = valor del propio mes M
BASELINE_COL = "prod_pet_lag0" if TARGET == "prod_pet" else "prod_gas_m"
MODEL_NAME = f"forecast_{TARGET}"

# columnas que no son features: índices, labels y la versión del feature set
NON_FEATURES = {
    "pozo_sk", "idpozo", "tiempo_sk", "fecha_mes",
    "target_prod_pet_m1", "target_prod_gas_m1", "feature_set_version",
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


def main():
    engine = create_engine(WAREHOUSE_DSN)
    df = pd.read_sql("select * from gold.feat_produccion_offline", engine)

    # filas de entrenamiento: target conocido (M+1 existe) y producción del mes M reportada
    train = df[df[TARGET_COL].notna() & df[BASELINE_COL].notna()].copy()
    if train.empty:
        raise SystemExit("Feature store sin filas de entrenamiento (¿corriste el pipeline de datos?).")

    feat_cols = [c for c in train.columns if c not in NON_FEATURES]
    cat_cols = [c for c in feat_cols if train[c].dtype == object]
    num_cols = [c for c in feat_cols if c not in cat_cols]

    # split TEMPORAL (no aleatorio): validación = el 20% de meses más recientes
    corte = train["fecha_mes"].quantile(0.8)
    tr, va = train[train["fecha_mes"] <= corte], train[train["fecha_mes"] > corte]
    if va.empty:  # datasets muy chicos
        tr = va = train

    pipe = build_pipeline(num_cols, cat_cols)
    pipe.fit(tr[feat_cols], tr[TARGET_COL])
    pred = pipe.predict(va[feat_cols])

    mae = mean_absolute_error(va[TARGET_COL], pred)
    rmse = root_mean_squared_error(va[TARGET_COL], pred)
    mae_base = mean_absolute_error(va[TARGET_COL], va[BASELINE_COL])  # baseline naive
    skill = 1 - mae / mae_base if mae_base else 0.0

    # --- MLflow: tracking + registry ---
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("oilgas-forecast")
    with mlflow.start_run(run_name=f"tracer-{TARGET}") as run:
        mlflow.log_params({
            "target": TARGET, "modelo": "DecisionTree(max_depth=4)",
            "n_train": len(tr), "n_valid": len(va), "n_features": len(feat_cols),
        })
        mlflow.log_metrics({"mae": mae, "rmse": rmse, "mae_baseline": mae_base, "skill_score": skill})
        mlflow.sklearn.log_model(pipe, artifact_path="model",
                                 signature=infer_signature(va[feat_cols], pred))
        run_id = run.info.run_id

    # registrar la versión y marcarla Production (alias) -> el serving la resuelve por alias
    client = MlflowClient(tracking_uri=TRACKING_URI)
    version = mlflow.register_model(f"runs:/{run_id}/model", MODEL_NAME).version
    client.set_registered_model_alias(MODEL_NAME, "Production", version)

    # --- inferencia: predecir M+1 desde el online store y escribir gold.fct_forecast ---
    model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@Production")
    online = pd.read_sql("select * from gold.feat_produccion_online", engine)
    online["prediccion"] = model.predict(online[feat_cols])

    out = online[["idpozo", "fecha_mes", "prediccion"]].rename(columns={"fecha_mes": "fecha_mes_base"})
    out["fecha_mes_pred"] = (pd.to_datetime(out["fecha_mes_base"]) + pd.DateOffset(months=1)).dt.date
    out["target_kind"] = TARGET
    out["model_name"] = MODEL_NAME
    out["model_version"] = version
    out.to_sql("fct_forecast", engine, schema="gold", if_exists="replace", index=False)

    print(f"[tracer] target={TARGET} | MAE={mae:.1f} baseline={mae_base:.1f} skill={skill:.3f} "
          f"| modelo {MODEL_NAME} v{version} -> Production | {len(out)} forecasts en gold.fct_forecast")


if __name__ == "__main__":
    main()
