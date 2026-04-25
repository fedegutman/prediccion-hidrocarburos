"""Unit tests para la logica de generacion de pronosticos."""

from datetime import date

from app.forecast.routes import _generate_forecast


def test_generate_forecast_returns_correct_number_of_days() -> None:
    """Verifica que se genera un punto por cada dia del rango."""
    points = _generate_forecast("POZO-001", date(2024, 1, 1), date(2024, 1, 3))
    assert len(points) == 3


def test_generate_forecast_same_day_returns_one_point() -> None:
    """Verifica que un rango de un solo dia retorna un punto."""
    points = _generate_forecast("POZO-001", date(2024, 1, 1), date(2024, 1, 1))
    assert len(points) == 1


def test_generate_forecast_production_decreases_over_time() -> None:
    """Verifica que la produccion decrece con el tiempo."""
    points = _generate_forecast("POZO-001", date(2024, 1, 1), date(2024, 1, 10))
    assert points[0].prod > points[-1].prod


def test_generate_forecast_production_never_negative() -> None:
    """Verifica que la produccion nunca es negativa aunque el rango sea muy largo."""
    points = _generate_forecast("POZO-001", date(2024, 1, 1), date(2030, 1, 1))
    assert all(p.prod >= 0.0 for p in points)


def test_generate_forecast_dates_are_sequential() -> None:
    """Verifica que las fechas de los puntos son consecutivas."""
    points = _generate_forecast("POZO-001", date(2024, 1, 1), date(2024, 1, 5))
    for i in range(1, len(points)):
        prev = date.fromisoformat(points[i - 1].date)
        curr = date.fromisoformat(points[i].date)
        assert (curr - prev).days == 1


def test_generate_forecast_first_date_matches_start() -> None:
    """Verifica que el primer punto corresponde a date_start."""
    points = _generate_forecast("POZO-001", date(2024, 3, 15), date(2024, 3, 17))
    assert points[0].date == "2024-03-15"


def test_generate_forecast_last_date_matches_end() -> None:
    """Verifica que el ultimo punto corresponde a date_end."""
    points = _generate_forecast("POZO-001", date(2024, 3, 15), date(2024, 3, 17))
    assert points[-1].date == "2024-03-17"


def test_generate_forecast_unknown_well_uses_default_production() -> None:
    """Verifica que un pozo desconocido usa produccion base por defecto (100.0)."""
    points = _generate_forecast("POZO-INEXISTENTE", date(2024, 1, 1), date(2024, 1, 1))
    assert points[0].prod == 100.0