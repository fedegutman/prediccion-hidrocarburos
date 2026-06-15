"""Tests del endpoint de pozos (datos reales de gold), con la DB mockeada.

No requieren un Postgres vivo: se mockea ``app.db.run_query`` para que corran
en CI de forma determinística. Las verificaciones de SQL real (incl. inyección)
están en ``test_integration_warehouse.py``.
"""

import psycopg
from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "test-api-key"}

_FAKE_POZO = {
    "idpozo": "10001",
    "sigla": "AB-1",
    "formacion_productiva": "Vaca Muerta",
    "area_yacimiento": "Loma Campana",
    "cuenca": "Neuquina",
    "provincia": "Neuquén",
    "tipo_reservorio": "No Convencional",
    "profundidad": 2500.0,
}


def test_list_pozos_returns_200(monkeypatch) -> None:
    """Con datos, lista pozos y responde 200."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [_FAKE_POZO])
    response = client.get("/api/v1/pozos", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["idpozo"] == "10001"
    assert body[0]["cuenca"] == "Neuquina"


def test_get_pozo_returns_200(monkeypatch) -> None:
    """Pedir un pozo existente por id retorna 200 con ese pozo."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [_FAKE_POZO])
    response = client.get("/api/v1/pozos/10001", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["idpozo"] == "10001"


def test_list_pozos_invalid_api_key_returns_403() -> None:
    """Una API key inválida retorna 403."""
    response = client.get("/api/v1/pozos", headers={"X-API-Key": "mala"})
    assert response.status_code == 403


def test_list_pozos_missing_api_key_returns_403() -> None:
    """Sin header de API key, retorna 403 (no se accede sin credencial)."""
    response = client.get("/api/v1/pozos")
    assert response.status_code == 403


def test_get_pozo_returns_404_when_missing(monkeypatch) -> None:
    """Pedir un pozo inexistente retorna 404."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [])
    response = client.get("/api/v1/pozos/99999", headers=HEADERS)
    assert response.status_code == 404


def test_pozos_rejects_out_of_range_pagination() -> None:
    """El paginado está acotado: protege contra pedir cantidades enormes (DoS).

    ``limit`` debe estar entre 1 y 1000, y ``offset`` no puede ser negativo.
    """
    assert client.get("/api/v1/pozos", params={"limit": 0}, headers=HEADERS).status_code == 422
    assert client.get("/api/v1/pozos", params={"limit": 1001}, headers=HEADERS).status_code == 422
    assert client.get("/api/v1/pozos", params={"offset": -1}, headers=HEADERS).status_code == 422


def test_pozos_returns_503_when_warehouse_down(monkeypatch) -> None:
    """Si el warehouse no está disponible, retorna 503."""

    def _boom(sql, params=None):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(db, "run_query", _boom)
    response = client.get("/api/v1/pozos", headers=HEADERS)
    assert response.status_code == 503


def test_pozos_503_does_not_leak_connection_details(monkeypatch) -> None:
    """El 503 no debe filtrar el DSN ni credenciales (information disclosure).

    Aunque la excepción interna contenga la cadena de conexión, la respuesta al
    cliente debe ser un mensaje genérico.
    """
    secret_dsn = "postgresql://dwh:supersecreto@10.0.0.5:5433/oilgas"

    def _boom(sql, params=None):
        raise psycopg.OperationalError(f"connection to {secret_dsn} failed")

    monkeypatch.setattr(db, "run_query", _boom)
    body = client.get("/api/v1/pozos", headers=HEADERS).text
    assert "postgresql://" not in body
    assert "supersecreto" not in body
    assert "10.0.0.5" not in body


def test_pozos_503_when_server_api_key_unset(monkeypatch) -> None:
    """SEGURIDAD: si el servidor no tiene API_KEY configurada, falla cerrado (503)."""
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get("/api/v1/pozos", headers=HEADERS)
    assert response.status_code == 503
