"""Helpers de ingesta a la capa Bronze del warehouse.

Vive en la carpeta `dags/` para que Airflow lo agregue automáticamente al PYTHONPATH
y los DAGs puedan importarlo (`import bronze_lib`).
"""

import hashlib
import os

import pandas as pd
import requests
from sqlalchemy import create_engine, inspect, text

# Conexión al warehouse. Por defecto apunta al servicio `warehouse` del docker-compose.
WAREHOUSE_URI = os.getenv(
    "WAREHOUSE_URI",
    "postgresql+psycopg2://dwh:dwh@warehouse:5432/oilgas",
)

_CHUNK = 200_000


def _engine():
    return create_engine(WAREHOUSE_URI)


# --- Metadata técnica de carga por registro (linaje / auditoría). Ver ADR-023. ---
# Columnas con prefijo _ para distinguirlas de las de negocio. Silver NO las consume
# (selecciona por nombre explícito), así que el contrato Bronze→Silver no cambia.
_META_DDL = (
    "_ingestion_ts timestamptz",
    "_source_url text",
    "_source_file text",
    "_batch_id text",
    "_load_type text",
    "_file_md5 text",
)


def _md5(path: str) -> str:
    """MD5 del archivo (streaming, no lo carga entero en memoria). Permite detectar si la
    fuente cambió entre corridas."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _with_metadata(df: pd.DataFrame, csv_path: str, source_url: str | None,
                   run_id: str | None, load_type: str) -> pd.DataFrame:
    """Enriquece el DataFrame con las columnas técnicas de carga (mismo valor para todas
    las filas de la corrida)."""
    return df.assign(
        _ingestion_ts=pd.Timestamp.now(tz="UTC"),
        _source_url=source_url,
        _source_file=os.path.basename(csv_path),
        _batch_id=run_id,
        _load_type=load_type,
        _file_md5=_md5(csv_path),
    )


def _ensure_meta_cols(conn, schema: str, table: str) -> None:
    """ALTER idempotente: agrega las columnas técnicas si la tabla YA existe sin ellas.
    Necesario porque to_sql(if_exists='append') NO agrega columnas nuevas a una tabla
    preexistente. En una tabla nueva no hace falta (to_sql la crea con las columnas)."""
    adds = ", ".join(f"ADD COLUMN IF NOT EXISTS {ddl}" for ddl in _META_DDL)
    conn.execute(text(f"ALTER TABLE {schema}.{table} {adds}"))


def download_csv(url: str, dest: str) -> str:
    """Descarga un CSV (streaming, para no cargarlo entero en memoria).

    :param url: URL del archivo.
    :param dest: ruta local donde guardarlo.
    :return: la ruta `dest`.
    """
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def load_full_replace(csv_path: str, schema: str, table: str,
                      source_url: str | None = None, run_id: str | None = None,
                      load_type: str = "full") -> int:
    """Carga FULL: reemplaza por completo el contenido de la tabla destino (snapshot).

    Usado para el listado de pozos (maestro de estado actual). Idempotente:
    correrlo N veces deja siempre el mismo contenido.

    Si la tabla ya existe, se vacía con TRUNCATE y se reinserta (NO se dropea):
    un DROP fallaría cuando hay vistas dependientes (ej. silver.stg_pozos),
    mientras que TRUNCATE conserva el objeto y la dependencia sigue válida.

    Cada fila se enriquece con metadata técnica de carga (ver ADR-023).

    :return: cantidad de filas cargadas.
    """
    df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
    df = _with_metadata(df, csv_path, source_url, run_id, load_type)
    eng = _engine()
    insp = inspect(eng)

    with eng.begin() as conn:
        if insp.has_table(table, schema=schema):
            _ensure_meta_cols(conn, schema, table)   # auto-migra tablas preexistentes
            conn.execute(text(f"TRUNCATE TABLE {schema}.{table}"))
            df.to_sql(table, conn, schema=schema, if_exists="append", index=False,
                      method="multi", chunksize=10_000)
        else:
            # primera vez: la tabla no existe, to_sql la crea (con las columnas técnicas)
            df.to_sql(table, conn, schema=schema, if_exists="replace", index=False,
                      method="multi", chunksize=10_000)

    return len(df)


def load_produccion_bronze(csv_path: str, date_from: str | None, date_to: str | None,
                           schema: str = "bronze", table: str = "produccion",
                           source_url: str | None = None, run_id: str | None = None,
                           load_type: str = "merge") -> int:
    """Carga INCREMENTAL con merge por período (idempotente).

    Lee el CSV por chunks (para no agotar memoria), filtra por rango de fechas
    construido desde anio+mes, y para los períodos (anio, mes) presentes:
    borra esos períodos en destino y reinserta. Así, reejecutar el mismo rango
    deja el mismo resultado y las rectificaciones pisan la versión anterior.

    Cada fila se enriquece con metadata técnica de carga (ver ADR-023).

    :param date_from: 'YYYY-MM-DD' inclusive (o None).
    :param date_to: 'YYYY-MM-DD' inclusive (o None).
    :return: cantidad de filas cargadas.
    """
    lo = pd.to_datetime(date_from) if date_from else None
    hi = pd.to_datetime(date_to) if date_to else None

    frames = []
    for chunk in pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False, chunksize=_CHUNK):
        period = pd.to_datetime(
            dict(year=chunk["anio"], month=chunk["mes"], day=1), errors="coerce"
        )
        mask = period.notna()
        if lo is not None:
            mask &= period >= lo
        if hi is not None:
            mask &= period <= hi
        sub = chunk[mask]
        if not sub.empty:
            frames.append(sub)

    if not frames:
        raise ValueError("No hay filas tras el filtro de fechas (revisar date_from/date_to).")

    df = pd.concat(frames, ignore_index=True)
    df = _with_metadata(df, csv_path, source_url, run_id, load_type)
    periods = df[["anio", "mes"]].drop_duplicates()

    eng = _engine()
    insp = inspect(eng)
    table_exists = insp.has_table(table, schema=schema)

    with eng.begin() as conn:
        if table_exists:
            _ensure_meta_cols(conn, schema, table)   # auto-migra tablas preexistentes
            for _, row in periods.iterrows():
                conn.execute(
                    text(f"DELETE FROM {schema}.{table} WHERE anio = :a AND mes = :m"),
                    {"a": int(row["anio"]), "m": int(row["mes"])},
                )
        df.to_sql(table, conn, schema=schema, if_exists="append", index=False,
                  method="multi", chunksize=10_000)

    return len(df)