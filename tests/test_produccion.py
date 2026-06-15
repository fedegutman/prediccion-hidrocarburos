"""Tests del endpoint de producción (datos reales de gold), con la DB mockeada.

No requieren un Postgres vivo: se mockea ``app.db.run_query`` para que corran
en CI de forma determinística. Las verificaciones de SQL real (incl. inyección)
están en ``test_integration_warehouse.py``.
"""

import psycopg
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "abcdef12345"}

_FAKE_ROW = {
    "idpozo": "10001",
    "anio": 2024,
    "mes": 1,
    "fecha_mes": "2024-01-01",
    "empresa": "YPF S.A.",
    "cuenca": "Neuquina",
    "provincia": "Neuquén",
    "area_yacimiento": "Loma Campana",
    "prod_pet": 1234.5,
    "prod_gas": 678.9,
    "prod_agua": 12.3,
}


def test_list_produccion_returns_200(monkeypatch) -> None:
    """Con datos, lista producción y responde 200."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [_FAKE_ROW])
    response = client.get("/api/v1/produccion", params={"anio": 2024}, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["anio"] == 2024
    assert body[0]["prod_pet"] == 1234.5


def test_produccion_invalid_api_key_returns_403() -> None:
    """Una API key inválida retorna 403."""
    response = client.get("/api/v1/produccion", headers={"X-API-Key": "mala"})
    assert response.status_code == 403


def test_produccion_missing_api_key_returns_403() -> None:
    """Sin header de API key, retorna 403."""
    response = client.get("/api/v1/produccion")
    assert response.status_code == 403


def test_produccion_empty_returns_200_empty_list(monkeypatch) -> None:
    """Sin resultados, retorna 200 con lista vacía (no es un error)."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [])
    response = client.get("/api/v1/produccion", params={"anio": 1900}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_produccion_rejects_out_of_range_pagination() -> None:
    """El paginado está acotado (protege contra pedir cantidades enormes)."""
    assert client.get("/api/v1/produccion", params={"limit": 0}, headers=HEADERS).status_code == 422
    assert client.get("/api/v1/produccion", params={"limit": 1001}, headers=HEADERS).status_code == 422
    assert client.get("/api/v1/produccion", params={"offset": -1}, headers=HEADERS).status_code == 422


def test_produccion_returns_503_when_warehouse_down(monkeypatch) -> None:
    """Si el warehouse no está disponible, retorna 503."""

    def _boom(sql, params=None):
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(db, "run_query", _boom)
    response = client.get("/api/v1/produccion", headers=HEADERS)
    assert response.status_code == 503


def test_produccion_503_does_not_leak_connection_details(monkeypatch) -> None:
    """El 503 no debe filtrar el DSN ni credenciales (information disclosure)."""
    secret_dsn = "postgresql://dwh:supersecreto@10.0.0.5:5433/oilgas"

    def _boom(sql, params=None):
        raise psycopg.OperationalError(f"connection to {secret_dsn} failed")

    monkeypatch.setattr(db, "run_query", _boom)
    body = client.get("/api/v1/produccion", headers=HEADERS).text
    assert "postgresql://" not in body
    assert "supersecreto" not in body
    assert "10.0.0.5" not in body
