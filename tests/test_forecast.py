"""Tests del endpoint de pronóstico de producción, con la DB mockeada.

El endpoint sirve las predicciones que el pipeline de ML persiste en
``gold.fct_forecast`` (ya no genera datos mock). Se mockea ``app.db.run_query``
para que corran en CI de forma determinística, sin un Postgres vivo.
"""

from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "test-api-key"}
PARAMS = {"id_well": "10001", "date_start": "2024-01-01", "date_end": "2024-03-31"}

_FAKE_ROWS = [
    {"fecha_mes_pred": "2024-01-01", "prediccion": 1234.5},
    {"fecha_mes_pred": "2024-02-01", "prediccion": 1100.0},
    {"fecha_mes_pred": "2024-03-01", "prediccion": 980.0},
]


def test_forecast_returns_200(monkeypatch) -> None:
    """Con predicciones disponibles, el endpoint responde 200."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: _FAKE_ROWS)
    response = client.get("/api/v1/forecast", params=PARAMS, headers=HEADERS)
    assert response.status_code == 200


def test_forecast_response_structure(monkeypatch) -> None:
    """La respuesta trae id_well, target y la lista de puntos."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: _FAKE_ROWS)
    response = client.get("/api/v1/forecast", params=PARAMS, headers=HEADERS)
    body = response.json()
    assert body["id_well"] == "10001"
    assert body["target"] == "prod_pet"  # default
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 3


def test_forecast_data_has_date_and_prod(monkeypatch) -> None:
    """Cada punto del pronóstico tiene date y prod."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: _FAKE_ROWS[:1])
    response = client.get("/api/v1/forecast", params=PARAMS, headers=HEADERS)
    point = response.json()["data"][0]
    assert "date" in point
    assert "prod" in point


def test_forecast_target_gas_is_reflected(monkeypatch) -> None:
    """El endpoint acepta target=prod_gas y lo refleja en la respuesta (multi-target)."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: _FAKE_ROWS)
    response = client.get(
        "/api/v1/forecast", params={**PARAMS, "target": "prod_gas"}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json()["target"] == "prod_gas"


def test_forecast_invalid_target_returns_422() -> None:
    """Un target fuera de {prod_pet, prod_gas} es rechazado por validación (422)."""
    response = client.get(
        "/api/v1/forecast", params={**PARAMS, "target": "prod_agua"}, headers=HEADERS
    )
    assert response.status_code == 422


def test_forecast_invalid_api_key_returns_403() -> None:
    """Una API key inválida retorna 403 (antes de tocar el warehouse)."""
    response = client.get(
        "/api/v1/forecast", params=PARAMS, headers={"X-API-Key": "clave-incorrecta"}
    )
    assert response.status_code == 403


def test_forecast_date_end_before_start_returns_400() -> None:
    """date_end anterior a date_start retorna 400 (antes de tocar el warehouse)."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "10001", "date_start": "2024-03-31", "date_end": "2024-01-01"},
        headers=HEADERS,
    )
    assert response.status_code == 400


def test_forecast_no_predictions_returns_404(monkeypatch) -> None:
    """Sin predicciones para el pozo/rango, retorna 404."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [])
    response = client.get("/api/v1/forecast", params=PARAMS, headers=HEADERS)
    assert response.status_code == 404


def test_forecast_warehouse_unavailable_returns_503(monkeypatch) -> None:
    """Si el warehouse no está disponible, retorna 503."""
    def boom(sql, params=None):
        raise RuntimeError("warehouse caído")

    monkeypatch.setattr(db, "run_query", boom)
    response = client.get("/api/v1/forecast", params=PARAMS, headers=HEADERS)
    assert response.status_code == 503


def test_forecast_invalid_date_format_returns_422() -> None:
    """Un formato de fecha inválido retorna 422 (validación de FastAPI)."""
    response = client.get(
        "/api/v1/forecast",
        params={"id_well": "10001", "date_start": "not-a-date", "date_end": "2024-03-31"},
        headers=HEADERS,
    )
    assert response.status_code == 422
