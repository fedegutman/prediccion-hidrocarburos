"""Rutas para el pronostico de produccion de pozos."""

import hmac
import os
from datetime import date
from typing import List, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from app.limiter import limiter
from app.metrics.business import FORECAST_REQUESTS_BY_WELL, FORECAST_DATE_RANGE_DAYS
from app import db

router = APIRouter()


class ForecastPoint(BaseModel):
    """Punto de producción estimada para un mes específico."""
    date: str
    prod: float


class ForecastResponse(BaseModel):
    """Pronóstico completo de producción para un pozo en un rango de fechas."""
    id_well: str
    target: str
    data: List[ForecastPoint]


def _validate_api_key(x_api_key: str) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Servicio mal configurado: falta API_KEY.")
    if not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=403, detail="Acceso denegado. API Key inválida.")


def _get_forecast_from_warehouse(
    id_well: str,
    date_start: date,
    date_end: date,
    target: str,
) -> List[ForecastPoint]:
    """Lee las predicciones de gold.fct_forecast para el pozo y target dados."""
    query = """
        SELECT fecha_mes_pred, prediccion
        FROM gold.fct_forecast
        WHERE idpozo = %(idpozo)s
          AND target_kind = %(target)s
          AND fecha_mes_pred BETWEEN %(date_start)s AND %(date_end)s
        ORDER BY fecha_mes_pred
    """
    try:
        rows = db.run_query(query, {
            "idpozo": id_well,
            "target": target,
            "date_start": date_start,
            "date_end": date_end,
        })
    except Exception:
        raise HTTPException(status_code=503, detail="Warehouse no disponible.")

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No hay predicciones para el pozo {id_well} con target {target} "
                   "en el rango dado. Verificá que el pipeline de entrenamiento haya corrido."
        )

    return [ForecastPoint(date=str(row["fecha_mes_pred"]), prod=round(float(row["prediccion"]), 2)) for row in rows]

@router.get(
    "/forecast",
    response_model=ForecastResponse,
    summary="Obtener pronóstico de producción",
    description="""
Retorna el pronóstico mensual de producción para un pozo dado en un rango de fechas.
Las predicciones son generadas por el modelo ML registrado en MLflow.

**Parámetros:**
- `id_well`: Identificador del pozo (idpozo en el warehouse)
- `date_start`: Fecha de inicio en formato `YYYY-MM-DD`
- `date_end`: Fecha de fin en formato `YYYY-MM-DD`
- `target`: Target a predecir — `prod_pet` (petróleo, default) o `prod_gas` (gas)

**Errores posibles:**
- `403` si la API key es inválida
- `400` si `date_end` es anterior a `date_start`
- `404` si no hay predicciones para el pozo en el rango dado
- `429` si se supera el límite de 60 requests por minuto
""",
)
@limiter.limit("60/minute")
def get_forecast(
    request: Request,
    id_well: str,
    date_start: date,
    date_end: date,
    target: Literal["prod_pet", "prod_gas"] = "prod_pet",
    x_api_key: str = Header(default=""),
) -> ForecastResponse:
    _validate_api_key(x_api_key)

    if date_end < date_start:
        raise HTTPException(status_code=400, detail="date_end no puede ser anterior a date_start.")

    FORECAST_REQUESTS_BY_WELL.labels(id_well=id_well).inc()
    FORECAST_DATE_RANGE_DAYS.observe((date_end - date_start).days)

    data = _get_forecast_from_warehouse(id_well, date_start, date_end, target)
    return ForecastResponse(id_well=id_well, target=target, data=data)