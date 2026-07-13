# Servicio MLflow (experiment tracking + model registry) — Fase 3.
# Imagen propia con versiones PINNEADAS para que corra igual en cualquier máquina
# (compañeros / profesores), sin depender de instalar nada en el host.
FROM python:3.12-slim

# mlflow + driver Postgres (backend store). psycopg2-binary trae wheels precompilados
# (no compila libpq), portable en Linux/Mac/Windows.
RUN pip install --no-cache-dir mlflow==2.18.0 psycopg2-binary==2.9.10

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
