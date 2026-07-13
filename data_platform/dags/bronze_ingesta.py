"""DAG de ingesta a Bronze: baja las dos fuentes de datos.gob.ar y las aterriza crudas.

- Producción (fact): carga incremental con merge por período (idempotente, reprocesable).
- Listado de pozos (dim maestro): carga full (reemplazo del snapshot).

Parametrizado por rango de fechas para permitir backfill / reproceso de un período.
Por defecto carga una ventana acotada (2023–2024) para que la demo sea rápida. Si
`date_from`/`date_to` se pasan en null, usa la ventana programada del DAG
(`data_interval`) y AVANZA mes a mes en operación recurrente (ver runbook data-engineer).
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
                           description="Inicio del período a cargar (YYYY-MM-DD). null = usar el data_interval del DAG (avanza mes a mes en operación programada)."),
        "date_to": Param("2024-12-31", type=["null", "string"],
                         description="Fin del período a cargar (YYYY-MM-DD). null = usar el data_interval del DAG."),
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
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        # Ventana de carga: si los params vienen en null, se usa la ventana programada
        # del DAG (data_interval) para que en operación recurrente AVANCE mes a mes.
        # Con los defaults (2023-01-01..2024-12-31) carga esa ventana fija para la demo.
        if date_from is None:
            date_from = context["data_interval_start"].strftime("%Y-%m-%d")
        if date_to is None:
            date_to = context["data_interval_end"].strftime("%Y-%m-%d")
        return bl.load_produccion_bronze(
            csv_path, date_from, date_to,
            source_url=PRODUCCION_URL, run_id=context.get("run_id"),
        )

    @task
    def load_pozos(csv_path: str, **context) -> int:
        import bronze_lib as bl
        return bl.load_full_replace(
            csv_path, schema="bronze", table="pozos",
            source_url=POZOS_URL, run_id=context.get("run_id"),
        )

    load_produccion(extract_produccion())
    load_pozos(extract_pozos())


bronze_ingesta()
