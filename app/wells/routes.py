"""Rutas para el listado de pozos disponibles."""

from datetime import date
from typing import List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from app.forecast.routes import _validate_api_key
from app.limiter import limiter
from app.mock_data import MOCK_WELLS


router = APIRouter()


class WellInfo(BaseModel):
    """Información de un pozo."""

    id_well: str
    nombre: str
    lugar: str
    active: bool

@router.get(
    "/wells",
    response_model=List[WellInfo],
    summary="Listado de pozos activos (mock, legacy — usar /pozos)",
    deprecated=True,
    description="""
**DEPRECADO (Fase 1, datos mock).** Usá `GET /api/v1/pozos`, que devuelve los
pozos reales del data warehouse (capa gold). Este endpoint se mantiene solo por
compatibilidad.

Retorna el listado de pozos activos para una fecha dada.

**Parámetros:**
- `date_query`: Fecha de consulta en formato `YYYY-MM-DD`

**Errores posibles:**
- `403` si la API key es inválida
- `404` si no hay pozos activos para la fecha dada
- `429` si se supera el límite de 60 requests por minuto
""",
)
@limiter.limit("60/minute")
def get_wells(request: Request, date_query: date, x_api_key: str = Header(default="")) -> List[WellInfo]:
    _validate_api_key(x_api_key)
    active_wells = [w for w in MOCK_WELLS if w["active"]]
    if not active_wells:
        raise HTTPException(status_code=404, detail="No hay pozos activos para la fecha dada.")
    return active_wells
