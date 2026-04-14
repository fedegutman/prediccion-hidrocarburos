"""Rutas para el pronostico de produccion de pozos."""

from datetime import date, timedelta
from typing import Dict, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

API_KEY = "abcdef12345"

router = APIRouter()

MOCK_BASE_PRODUCTION: Dict[str, float] = {
    "POZO-001": 150.0,
    "POZO-002": 210.5,
    "POZO-003": 98.3,
    "POZO-004": 175.0,
    "POZO-005": 320.8,
}

DAILY_DECLINE: float = 0.5


class ForecastPoint(BaseModel):
    """Punto de pronostico para una fecha dada.

    :param date: Fecha del pronostico (YYYY-MM-DD).
    :param prod: Produccion esperada en ese dia.
    """

    date: str
    prod: float


class ForecastResponse(BaseModel):
    """Respuesta del endpoint de pronostico.

    :param id_well: Identificador del pozo.
    :param data: Lista de puntos de pronostico diario.
    """

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


@router.get("/forecast", response_model=ForecastResponse)
def get_forecast(
    id_well: str,
    date_start: date,
    date_end: date,
    x_api_key: str = Header(default=""),
) -> ForecastResponse:
    """Obtiene el pronostico de produccion de un pozo para un horizonte de tiempo.

    :param id_well: Identificador del pozo.
    :param date_start: Fecha de inicio del pronostico (YYYY-MM-DD).
    :param date_end: Fecha de fin del pronostico (YYYY-MM-DD).
    :param x_api_key: API key de autenticacion (header X-API-Key).
    :return: Pronostico diario de produccion para el pozo.
    :raises HTTPException: Si la API key es invalida (403).
    :raises HTTPException: Si date_end es anterior a date_start (400).
    """
    _validate_api_key(x_api_key)

    if date_end < date_start:
        raise HTTPException(status_code=400, detail="date_end no puede ser anterior a date_start.")

    data = _generate_forecast(id_well, date_start, date_end)
    return ForecastResponse(id_well=id_well, data=data)
