"""Tests para el endpoint de metricas de Prometheus."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "test-api-key"}


def test_metrics_endpoint_returns_200() -> None:
    """Verifica que el endpoint /metrics responde correctamente."""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_returns_prometheus_format() -> None:
    """Verifica que la respuesta tiene formato Prometheus (text/plain)."""
    response = client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]


def test_metrics_expone_http_requests_total() -> None:
    """Verifica que la metrica de requests HTTP esta presente."""
    client.get("/api/v1/wells", params={"date_query": "2024-01-01"}, headers=HEADERS)
    response = client.get("/metrics")
    assert "http_requests_total" in response.text


def test_metrics_expone_http_request_duration_seconds() -> None:
    """Verifica que la metrica de latencia HTTP esta presente."""
    response = client.get("/metrics")
    assert "http_request_duration_seconds" in response.text


def test_metrics_expone_forecast_requests_by_well() -> None:
    """Verifica que la metrica de negocio de pronósticos por pozo esta presente."""
    client.get(
        "/api/v1/forecast",
        params={"id_well": "POZO-001", "date_start": "2024-01-01", "date_end": "2024-01-03"},
        headers=HEADERS,
    )
    response = client.get("/metrics")
    assert "forecast_requests_by_well_total" in response.text
