"""Tests para el endpoint de health check."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    """Verifica que el endpoint /health responde correctamente."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_body() -> None:
    """Verifica que /health retorna el estado esperado por el CD."""
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
