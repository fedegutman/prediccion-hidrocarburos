"""Tests de INTEGRACIÓN contra el warehouse real (capa gold).

Se SALTEAN automáticamente si el warehouse no está accesible (p. ej. en CI, que
no levanta Postgres) y corren localmente cuando está disponible. Son los que de
verdad ejercitan el SQL: los unit tests mockean la DB y NO detectan errores de
consulta ni problemas de seguridad como la inyección SQL.
"""

import socket

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


def _warehouse_disponible() -> bool:
    """True si el warehouse responde en localhost:5433."""
    try:
        with socket.create_connection(("localhost", 5433), timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _warehouse_disponible(),
    reason="warehouse (localhost:5433) no disponible; correr 'docker compose up -d' en data_platform",
)

client = TestClient(app)
HEADERS = {"X-API-Key": "test-api-key"}


def test_produccion_devuelve_datos_reales() -> None:
    """El endpoint trae filas reales con la forma esperada del modelo estrella."""
    response = client.get("/api/v1/produccion", params={"limit": 3}, headers=HEADERS)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert {"idpozo", "anio", "mes", "fecha_mes", "prod_pet"} <= set(rows[0])


def test_pozos_filtro_provincia_real() -> None:
    """El filtro por provincia se aplica realmente en la consulta."""
    response = client.get(
        "/api/v1/pozos", params={"provincia": "Neuquén", "limit": 5}, headers=HEADERS
    )
    assert response.status_code == 200
    assert all(p["provincia"] == "Neuquén" for p in response.json())


def test_inyeccion_sql_neutralizada_en_filtro() -> None:
    """SEGURIDAD: un payload de inyección se trata como literal, no como SQL.

    Si el filtro fuera vulnerable, ``' OR '1'='1`` haría que la condición sea
    siempre verdadera y devolvería TODOS los pozos. Con parametrización, se busca
    una provincia que literalmente se llame así -> no matchea -> lista vacía.
    """
    payload = "' OR '1'='1"
    response = client.get(
        "/api/v1/pozos", params={"provincia": payload, "limit": 5}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json() == []


def test_inyeccion_sql_no_ejecuta_comandos() -> None:
    """SEGURIDAD: un intento de DROP via parámetro no se ejecuta.

    La tabla debe conservar sus filas antes y después del request.
    """
    antes = db.run_query("select count(*) as n from gold.dim_pozo")[0]["n"]
    payload = "'; drop table gold.dim_pozo; --"
    response = client.get("/api/v1/pozos", params={"provincia": payload}, headers=HEADERS)
    assert response.status_code == 200
    despues = db.run_query("select count(*) as n from gold.dim_pozo")[0]["n"]
    assert antes == despues
    assert antes > 0
