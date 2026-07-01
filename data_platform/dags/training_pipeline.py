"""DAG de entrenamiento: entrena el modelo de forecast y lo registra en MLflow.

Se dispara automáticamente después de que dbt_transform termina exitosamente,
o manualmente desde la UI de Airflow para un período dado.

Flujo:
  1. wait_for_gold    -> espera que dbt_transform haya promovido Gold exitosamente.
  2. train_pet        -> entrena modelo de prod_pet y registra en MLflow.
  3. train_gas        -> entrena modelo de prod_gas y registra en MLflow (en paralelo).

Al terminar, gold.fct_forecast tiene las predicciones del próximo mes para cada pozo.
"""

import os
from datetime import datetime, timedelta

from airflow.sdk import dag, task
from airflow.sensors.external_task import ExternalTaskSensor

WAREHOUSE_DSN = os.getenv(
    "WAREHOUSE_DSN",
    "postgresql://dwh:dwh@warehouse:5432/oilgas",
)
MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://mlflow:5000",
)
TRACER_PATH = "/opt/airflow/ml/tracer_bullet.py"


def _run_tracer(target: str) -> str:
    """Corre el tracer bullet para un target dado. Lanza excepción si falla."""
    import subprocess

    result = subprocess.run(
        ["python", TRACER_PATH],
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "TARGET": target,
            "WAREHOUSE_DSN": WAREHOUSE_DSN,
            "MLFLOW_TRACKING_URI": MLFLOW_TRACKING_URI,
        },
    )
    print(result.stdout)
    if result.returncode != 0:
        raise Exception(f"Training {target} falló:\n{result.stderr}\n{result.stdout}")
    return result.stdout


@dag(
    dag_id="training_pipeline",
    description="Entrena modelos de forecast (prod_pet y prod_gas) y los registra en MLflow",
    start_date=datetime(2024, 1, 1),
    schedule="@monthly",
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["fase3", "ml", "training", "mlflow"],
)
def training_pipeline():

    wait_for_gold = ExternalTaskSensor(
        task_id="wait_for_dbt_transform",
        external_dag_id="dbt_transform",
        timeout=3600,
        poke_interval=30,
        mode="poke",
    )

    @task
    def train_pet() -> str:
        """Entrena el modelo de producción de petróleo y lo registra en MLflow."""
        return _run_tracer("prod_pet")

    @task
    def train_gas() -> str:
        """Entrena el modelo de producción de gas y lo registra en MLflow."""
        return _run_tracer("prod_gas")

    # train_pet y train_gas corren en paralelo después de que Gold está listo
    wait_for_gold >> [train_pet(), train_gas()]


training_pipeline()