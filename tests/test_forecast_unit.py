"""Unit tests para la lógica de lectura de pronósticos desde el warehouse.

El endpoint de forecast dejó de generar datos mock: ahora lee las predicciones
que el pipeline de ML persiste en ``gold.fct_forecast``. Estos tests ejercitan
``_get_forecast_from_warehouse`` con ``app.db.run_query`` mockeado, sin necesidad
de un Postgres vivo.
"""

from datetime import date

import pytest
from fastapi import HTTPException

from app import db
from app.forecast.routes import _get_forecast_from_warehouse, _validate_api_key


def _rows(*pairs):
    """Arma filas con la forma que devuelve ``db.run_query`` para fct_forecast."""
    return [{"fecha_mes_pred": d, "prediccion": p} for d, p in pairs]


def test_forecast_maps_rows_to_points(monkeypatch) -> None:
    """Cada fila del warehouse se mapea a un ForecastPoint con la predicción redondeada."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: _rows(
        ("2024-01-01", 1234.567), ("2024-02-01", 1000.0),
    ))
    points = _get_forecast_from_warehouse("10001", date(2024, 1, 1), date(2024, 12, 31), "prod_pet")
    assert len(points) == 2
    assert points[0].date == "2024-01-01"
    assert points[0].prod == 1234.57  # redondeado a 2 decimales


def test_forecast_passes_target_and_pozo_to_query(monkeypatch) -> None:
    """El pozo y el target recibidos se pasan como parámetros de la consulta (multi-target)."""
    captured = {}

    def fake_run_query(sql, params=None):
        captured.update(params or {})
        return _rows(("2024-01-01", 10.0))

    monkeypatch.setattr(db, "run_query", fake_run_query)
    _get_forecast_from_warehouse("10001", date(2024, 1, 1), date(2024, 12, 31), "prod_gas")
    assert captured["target"] == "prod_gas"
    assert captured["idpozo"] == "10001"


def test_forecast_no_rows_raises_404(monkeypatch) -> None:
    """Sin predicciones para el pozo/rango, lanza 404."""
    monkeypatch.setattr(db, "run_query", lambda sql, params=None: [])
    with pytest.raises(HTTPException) as exc:
        _get_forecast_from_warehouse("99999", date(2024, 1, 1), date(2024, 12, 31), "prod_pet")
    assert exc.value.status_code == 404


def test_forecast_db_error_raises_503(monkeypatch) -> None:
    """Si el warehouse no está disponible, lanza 503."""
    def boom(sql, params=None):
        raise RuntimeError("warehouse caído")

    monkeypatch.setattr(db, "run_query", boom)
    with pytest.raises(HTTPException) as exc:
        _get_forecast_from_warehouse("10001", date(2024, 1, 1), date(2024, 12, 31), "prod_pet")
    assert exc.value.status_code == 503


def test_validate_api_key_ok() -> None:
    """La API key correcta (seteada en conftest) no lanza excepción."""
    _validate_api_key("test-api-key")


def test_validate_api_key_invalid_raises_403() -> None:
    """Una API key incorrecta lanza 403."""
    with pytest.raises(HTTPException) as exc:
        _validate_api_key("clave-incorrecta")
    assert exc.value.status_code == 403
