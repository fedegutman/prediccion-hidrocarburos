# Imagen del módulo ML (entrenamiento/inferencia) — Fase 3.
# Versiones pinneadas para que corra igual en cualquier máquina (compañeros / profesores).
FROM python:3.12-slim

RUN pip install --no-cache-dir \
    mlflow==2.18.0 \
    scikit-learn==1.5.2 \
    pandas==2.2.3 \
    sqlalchemy==2.0.36 \
    psycopg2-binary==2.9.10

WORKDIR /app
COPY . /app

# Por defecto corre el tracer bullet; WS5/WS6 reutilizarán este módulo desde Airflow.
CMD ["python", "tracer_bullet.py"]
