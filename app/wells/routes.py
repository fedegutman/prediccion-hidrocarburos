"""Rutas para el listado de pozos disponibles."""

from typing import List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.forecast.routes import API_KEY, MOCK_BASE_PRODUCTION, _validate_api_key

router = APIRouter()

MOCK_WELLS = [
    {"id_well": "POZO-001", "field": "Neuquen", "basin": "Neuquina", "active": True},
    {"id_well": "POZO-002", "field": "Neuquen", "basin": "Neuquina", "active": True},
    {"id_well": "POZO-003", "field": "Mendoza", "basin": "Cuyana", "active": False},
    {"id_well": "POZO-004", "field": "Chubut",  "basin": "San Jorge", "active": True},
    {"id_well": "POZO-005", "field": "Neuquen", "basin": "Neuquina", "active": True},
]

class WellInfo(BaseModel):
    """Informacion de un pozo.

    :param id_well: Identificador del pozo.
    :param field: Campo al que pertenece el pozo.
    :param basin: Cuenca geologica del pozo.
    :param active: Indica si el pozo esta activo.
    """

    id_well: str
    field: str
    basin: str
    active: bool

@router.get("/wells", response_model=List[WellInfo])
def get_wells(date_query: str, x_api_key: str = Header(default="")) -> List[WellInfo]:
    """
    Obtiene el listado de pozos disponibles para una fecha dada.

    :param date_query: Fecha para la cual se hace la consulta (YYYY-MM-DD).
    :param x_api_key: API key de autenticacion (header X-API-Key).
    :return: Lista de pozos disponibles.
    :raises HTTPException: Si la API key es invalida (403).
    """
    _validate_api_key(x_api_key)
    return MOCK_WELLS
