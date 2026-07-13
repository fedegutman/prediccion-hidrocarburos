#!/usr/bin/env bash
# Arranque de MLflow: espera al Postgres del warehouse, crea la base `mlflow` si no existe
# (idempotente, funciona sobre volúmenes nuevos Y existentes), y levanta el tracking server.
# Todo configurable por env vars (con defaults que matchean el docker-compose) para portabilidad.
set -e

# Espera a Postgres y crea la base de MLflow si falta (usando psycopg2, sin cliente psql).
python - <<'PY'
import os, time, psycopg2

host = os.getenv("MLFLOW_DB_HOST", "warehouse")
port = int(os.getenv("MLFLOW_DB_PORT", "5432"))
user = os.getenv("MLFLOW_DB_USER", "dwh")
pw   = os.getenv("MLFLOW_DB_PASSWORD", "dwh")
db   = os.getenv("MLFLOW_DB_NAME", "mlflow")

for intento in range(60):
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=pw, dbname="postgres")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("select 1 from pg_database where datname = %s", (db,))
        if cur.fetchone() is None:
            cur.execute(f'create database "{db}"')
            print(f"[mlflow] base '{db}' creada")
        else:
            print(f"[mlflow] base '{db}' ya existe")
        cur.close(); conn.close()
        break
    except Exception as e:
        print(f"[mlflow] esperando Postgres ({host}:{port})... {e}")
        time.sleep(2)
else:
    raise SystemExit("[mlflow] no se pudo conectar al Postgres del warehouse")
PY

mkdir -p "${MLFLOW_ARTIFACTS:-/mlflow/artifacts}"

# MLflow crea/migra sus tablas en el backend automáticamente al arrancar.
exec mlflow server \
  --backend-store-uri "postgresql://${MLFLOW_DB_USER:-dwh}:${MLFLOW_DB_PASSWORD:-dwh}@${MLFLOW_DB_HOST:-warehouse}:${MLFLOW_DB_PORT:-5432}/${MLFLOW_DB_NAME:-mlflow}" \
  --artifacts-destination "${MLFLOW_ARTIFACTS:-/mlflow/artifacts}" \
  --host 0.0.0.0 \
  --port "${MLFLOW_PORT:-5000}"
