"""DAG de ingesta a Bronze: baja las dos fuentes de datos.gob.ar y las aterriza crudas.

- Producción (fact): carga incremental con merge por período (idempotente, reprocesable).
- Listado de pozos (dim maestro): carga full (reemplazo del snapshot).

Parametrizado por rango de fechas para permitir backfill / reproceso de un período.
Por defecto carga una ventana acotada (2023–2024) para que la demo sea rápida.
"""

from datetime import datetime, timedelta

from airflow.sdk import Param, dag, task

PRODUCCION_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/"
    "resource/b5b58cdc-9e07-41f9-b392-fb9ec68b0725/download/"
    "produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv"
)
POZOS_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/"
    "resource/cbfa4d79-ffb3-4096-bab5-eb0dde9a8385/download/"
    "listado-de-pozos-cargados-por-empresas-operadoras.csv"
)


@dag(
    dag_id="bronze_ingesta",
    description="Extracción de fuentes datos.gob.ar a la capa Bronze del warehouse",
    start_date=datetime(2024, 1, 1),
    schedule="@monthly",
    catchup=False,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=1),
        "retry_exponential_backoff": True,      # backoff: 1m, 2m, 4m...
        "max_retry_delay": timedelta(minutes=10),
    },
    params={
        "date_from": Param("2023-01-01", type=["null", "string"],
                           description="Fecha inicio del período a cargar (YYYY-MM-DD)"),
        "date_to": Param("2024-12-31", type=["null", "string"],
                         description="Fecha fin del período a cargar (YYYY-MM-DD). null = sin tope"),
    },
    tags=["fase2", "bronze"],
)
def bronze_ingesta():

    @task
    def extract_produccion() -> str:
        import bronze_lib as bl
        return bl.download_csv(PRODUCCION_URL, "/tmp/produccion.csv")

    @task
    def extract_pozos() -> str:
        import bronze_lib as bl
        return bl.download_csv(POZOS_URL, "/tmp/pozos.csv")

    @task
    def load_produccion(csv_path: str, **context) -> int:
        import bronze_lib as bl
        params = context["params"]
        return bl.load_produccion_bronze(csv_path, params.get("date_from"), params.get("date_to"))

    @task
    def load_pozos(csv_path: str) -> int:
        import bronze_lib as bl
        return bl.load_full_replace(csv_path, schema="bronze", table="pozos")

    load_produccion(extract_produccion())
    load_pozos(extract_pozos())


bronze_ingesta()
