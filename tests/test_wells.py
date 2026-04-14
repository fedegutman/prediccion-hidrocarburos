"""Tests para el endpoint de listado de pozos."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "abcdef12345"}


def test_wells_returns_200() -> None:
    """Verifica que el endpoint retorna 200 con parametros validos."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2024-01-01"},
        headers=HEADERS,
    )
    assert response.status_code == 200


def test_wells_returns_list() -> None:
    """Verifica que la respuesta es una lista de pozos."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2024-01-01"},
        headers=HEADERS,
    )
    body = response.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_wells_returns_list_of_objects() -> None:
    """Verifica que la respuesta es una lista de objetos."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2024-01-01"},
        headers=HEADERS,
    )
    body = response.json()
    assert isinstance(body, list)
    assert isinstance(body[0], dict)


def test_wells_only_returns_active() -> None:
    """Verifica que solo retorna pozos activos."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2024-01-01"},
        headers=HEADERS,
    )
    for well in response.json():
        assert well["active"] is True


def test_wells_invalid_api_key_returns_403() -> None:
    """Verifica que una API key invalida retorna 403."""
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2024-01-01"},
        headers={"X-API-Key": "clave-incorrecta"},
    )
    assert response.status_code == 403