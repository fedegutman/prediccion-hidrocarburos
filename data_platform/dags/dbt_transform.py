"""DAG de transformación: corre dbt build para transformar Bronze → Silver → Gold.
Se dispara automáticamente después de que bronze_ingesta termina exitosamente.
"""

from datetime import datetime, timedelta
from airflow.sdk import dag, task
from airflow.sensors.external_task import ExternalTaskSensor


@dag(
    dag_id="dbt_transform",
    description="Transforma Bronze → Silver → Gold via dbt",
    start_date=datetime(2024, 1, 1),
    schedule="@monthly",
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
    },
    tags=["fase2", "silver", "gold", "dbt"],
)
def dbt_transform():

    wait_for_bronze = ExternalTaskSensor(
        task_id="wait_for_bronze_ingesta",
        external_dag_id="bronze_ingesta",
        timeout=3600,
        poke_interval=30,
        mode="poke",
    )

    @task
    def run_dbt_build() -> str:
        import subprocess
        result = subprocess.run(
            [
                "dbt", "build",
                "--project-dir", "/opt/airflow/dbt/oilgas",
                "--profiles-dir", "/opt/airflow/dbt/oilgas",
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            raise Exception(f"dbt build falló:\n{result.stderr}")
        return result.stdout

    wait_for_bronze >> run_dbt_build()


dbt_transform()