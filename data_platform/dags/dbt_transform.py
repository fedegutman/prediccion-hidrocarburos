"""DAG de transformación: Bronze → Silver → Gold con promoción Write-Audit-Publish.

En vez de un `dbt build` plano que materializa Gold en el schema vivo ANTES de testearlo
(con lo cual un dato roto queda expuesto a la API/BI hasta la próxima corrida), la promoción
es en cuatro pasos con gate de calidad real (ver ADR-022):

  1. build_silver        -> construye las vistas Silver y corre sus tests de calidad.
  2. build_gold_staging  -> materializa Gold en un schema STAGING (gold_staging), no en el vivo.
  3. test_gold_staging   -> corre los tests de Gold contra el staging.
  4. swap_gold           -> SOLO si todo pasó (trigger_rule=all_success), swap atómico
                            gold_staging -> gold. Si algún test ERROR falla, `gold` queda
                            intacto en su última versión buena y el DAG falla (alerta).

Se dispara automáticamente después de que bronze_ingesta termina exitosamente.
"""

import os
from datetime import datetime, timedelta

from airflow.sdk import dag, task
from airflow.sensors.external_task import ExternalTaskSensor

DBT_DIR = "/opt/airflow/dbt/oilgas"
STAGING_SCHEMA = "gold_staging"
# Mismo default que bronze_lib: dbt y el swap apuntan al servicio `warehouse` del compose.
WAREHOUSE_URI = os.getenv(
    "WAREHOUSE_URI",
    "postgresql+psycopg2://dwh:dwh@warehouse:5432/oilgas",
)


def _run_dbt(args: list[str]) -> str:
    """Corre un comando dbt en el proyecto oilgas. Lanza excepción si dbt devuelve != 0
    (un test de calidad ERROR roto frena la tarea y, por la cadena, la promoción a gold)."""
    import subprocess

    result = subprocess.run(
        ["dbt", *args, "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        raise Exception(f"dbt {' '.join(args)} falló:\n{result.stderr}\n{result.stdout}")
    return result.stdout


def _drop_schema(schema: str) -> None:
    """Elimina un schema (y su contenido) si existe. Se usa para limpiar el staging de
    corridas previas antes de reconstruirlo."""
    from sqlalchemy import create_engine, text

    eng = create_engine(WAREHOUSE_URI)
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))


@dag(
    dag_id="dbt_transform",
    description="Transforma Bronze → Silver → Gold via dbt con gate de calidad (WAP)",
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
    def build_silver() -> str:
        """Construye Silver (vistas) y corre sus tests. Silver son VISTAS, no las consume
        la API directamente; si un test ERROR de Silver falla, frena acá la promoción."""
        return _run_dbt(["build", "--select", "silver"])

    @task
    def build_gold_staging() -> str:
        """Materializa Gold en gold_staging (NO en el schema vivo). Limpia el staging previo
        para no arrastrar tablas de corridas fallidas."""
        _drop_schema(STAGING_SCHEMA)
        return _run_dbt(
            ["run", "--select", "gold", "--vars", '{"gold_schema": "gold_staging"}']
        )

    @task
    def test_gold_staging() -> str:
        """Corre los tests de calidad de Gold contra el staging. Si un test ERROR falla,
        el swap NO se ejecuta (trigger_rule=all_success aguas abajo)."""
        return _run_dbt(
            ["test", "--select", "gold", "--vars", '{"gold_schema": "gold_staging"}']
        )

    @task
    def swap_gold() -> None:
        """Swap atómico gold_staging -> gold (en una transacción). Solo corre si build+test
        de Gold pasaron. Si `gold` no existe (primera corrida), se omite el rename del viejo."""
        from sqlalchemy import create_engine, text

        eng = create_engine(WAREHOUSE_URI)
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS gold_old CASCADE"))
            # Renombra el gold vivo a gold_old solo si existe (primera corrida no tiene gold).
            conn.execute(
                text(
                    "DO $$ BEGIN "
                    "IF EXISTS (SELECT 1 FROM information_schema.schemata "
                    "WHERE schema_name = 'gold') THEN "
                    "EXECUTE 'ALTER SCHEMA gold RENAME TO gold_old'; "
                    "END IF; END $$;"
                )
            )
            conn.execute(text("ALTER SCHEMA gold_staging RENAME TO gold"))
            conn.execute(text("DROP SCHEMA IF EXISTS gold_old CASCADE"))

    silver = build_silver()
    staging = build_gold_staging()
    tested = test_gold_staging()
    swapped = swap_gold()

    wait_for_bronze >> silver >> staging >> tested >> swapped


dbt_transform()
