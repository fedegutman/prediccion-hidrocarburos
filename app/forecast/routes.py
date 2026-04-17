"""Rutas para el pronostico de produccion de pozos."""

from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from app.limiter import limiter
from app.mock_data import MOCK_WELLS, MOCK_BASE_PRODUCTION, DAILY_DECLINE
from app.metrics.business import FORECAST_REQUESTS_BY_WELL, FORECAST_DATE_RANGE_DAYS


API_KEY = "abcdef12345"

router = APIRouter()


class ForecastPoint(BaseModel):
    """Punto de producción estimada para un día específico."""

    date: str
    prod: float


class ForecastResponse(BaseModel):
    """Pronóstico completo de producción para un pozo en un rango de fechas."""

    id_well: str
    data: List[ForecastPoint]


def _validate_api_key(x_api_key: str) -> None:
    """Valida que la API key sea correcta.

    :param x_api_key: API key recibida en el header.
    :raises HTTPException: Si la API key es invalida o esta ausente (403).
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Acceso denegado. API Key invalida o faltante en el header.")


def _generate_forecast(id_well: str, date_start: date, date_end: date) -> List[ForecastPoint]:
    """Genera una lista de puntos de pronostico con tendencia lineal decreciente.

    :param id_well: Identificador del pozo.
    :param date_start: Fecha de inicio del pronostico.
    :param date_end: Fecha de fin del pronostico.
    :return: Lista de puntos de pronostico diario.
    """
    base = MOCK_BASE_PRODUCTION.get(id_well, 100.0)
    points = []
    current = date_start
    day = 0
    while current <= date_end:
        prod = max(0.0, base - DAILY_DECLINE * day)
        points.append(ForecastPoint(date=current.isoformat(), prod=round(prod, 2)))
        current += timedelta(days=1)
        day += 1
    return points


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Obtener pronóstico de producción",
    description="""
Retorna el pronóstico diario de producción para un pozo dado en un rango de fechas.

**Parámetros:**
- `id_well`: Identificador del pozo (ej: `POZO-001`)
- `date_start`: Fecha de inicio en formato `YYYY-MM-DD`
- `date_end`: Fecha de fin en formato `YYYY-MM-DD`

**Errores posibles:**
- `403` si la API key es inválida
- `400` si `date_end` es anterior a `date_start`
- `404` si el pozo no existe
- `429` si se supera el límite de 60 requests por minuto

""",
)
@limiter.limit("60/minute")
def get_forecast(
    request: Request,
    id_well: str,
    date_start: date,
    date_end: date,
    x_api_key: str = Header(default=""),
) -> ForecastResponse:
    _validate_api_key(x_api_key)

    if id_well not in [w["id_well"] for w in MOCK_WELLS]:
        raise HTTPException(status_code=404, detail=f"El pozo {id_well} no existe.")

    if date_end < date_start:
        raise HTTPException(status_code=400, detail="date_end no puede ser anterior a date_start.")

    FORECAST_REQUESTS_BY_WELL.labels(id_well=id_well).inc()
    FORECAST_DATE_RANGE_DAYS.observe((date_end - date_start).days)

    data = _generate_forecast(id_well, date_start, date_end)
    return ForecastResponse(id_well=id_well, data=data)
