"""Tests para el endpoint de pronostico de produccion."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "abcdef12345"}


def test_forecast_returns_200() -> None:
    """Verifica que el endpoint retorna 200 con parametros validos."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-001", "date_start": "2024-01-01", "date_end": "2024-01-03"},
        headers=HEADERS,
    )
    assert response.status_code == 200


def test_forecast_response_structure() -> None:
    """Verifica que la respuesta tiene la estructura correcta."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-001", "date_start": "2024-01-01", "date_end": "2024-01-03"},
        headers=HEADERS,
    )
    body = response.json()
    assert "id_well" in body
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 3


def test_forecast_data_has_date_and_prod() -> None:
    """Verifica que cada punto del pronostico tiene date y prod."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-001", "date_start": "2024-01-01", "date_end": "2024-01-01"},
        headers=HEADERS,
    )
    point = response.json()["data"][0]
    assert "date" in point
    assert "prod" in point


def test_forecast_invalid_api_key_returns_403() -> None:
    """Verifica que una API key invalida retorna 403."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-001", "date_start": "2024-01-01", "date_end": "2024-01-03"},
        headers={"X-API-Key": "clave-incorrecta"},
    )
    assert response.status_code == 403


def test_forecast_date_end_before_start_returns_400() -> None:
    """Verifica que date_end anterior a date_start retorna 400."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-001", "date_start": "2024-01-10", "date_end": "2024-01-01"},
        headers=HEADERS,
    )
    assert response.status_code == 400


def test_forecast_well_not_found_returns_404() -> None:
    """Verifica que un pozo inexistente retorna 404."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-999", "date_start": "2024-01-01", "date_end": "2024-01-03"},
        headers=HEADERS,
    )
    assert response.status_code == 404