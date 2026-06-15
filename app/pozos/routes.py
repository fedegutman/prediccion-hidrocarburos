"""Rutas de solo lectura para los pozos del data warehouse (``gold.dim_pozo``).

Exponen el maestro de pozos *con sus campos reales* de la capa gold (ya limpia
y tipada), siguiendo el modelo de "data product": direccionable y
self-describing. Es de solo lectura: la API nunca modifica el warehouse.
"""

from typing import List, Optional

import psycopg
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel
from starlette.requests import Request

from app import db
from app.forecast.routes import _validate_api_key
from app.limiter import limiter

router = APIRouter()


class Pozo(BaseModel):
    """Pozo del maestro con sus atributos reales de gold (``gold.dim_pozo``).

    :param idpozo: Identificador del pozo (clave natural).
    :param sigla: Sigla del pozo.
    :param formacion_productiva: Formación productiva.
    :param area_yacimiento: Área o yacimiento.
    :param cuenca: Cuenca.
    :param provincia: Provincia.
    :param tipo_reservorio: Tipo de reservorio.
    :param profundidad: Profundidad registrada.
    """

    idpozo: str
    sigla: Optional[str] = None
    formacion_productiva: Optional[str] = None
    area_yacimiento: Optional[str] = None
    cuenca: Optional[str] = None
    provincia: Optional[str] = None
    tipo_reservorio: Optional[str] = None
    profundidad: Optional[float] = None


_SELECT_POZO = """
    select
        idpozo::text          as idpozo,
        sigla,
        formacion_productiva,
        area_yacimiento,
        cuenca,
        provincia,
        tipo_reservorio,
        profundidad
    from gold.dim_pozo
"""


def _fetch(sql: str, params: Optional[dict] = None) -> List[dict]:
    """Ejecuta la consulta y traduce la caída del warehouse a un 503.

    :param sql: Consulta SQL parametrizada.
    :param params: Parámetros de la consulta.
    :return: Filas como lista de dicts.
    :raises HTTPException: 503 si el data warehouse no está disponible.
    """
    try:
        return db.run_query(sql, params)
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail="El data warehouse no está disponible.") from exc


@router.get(
    "/pozos",
    response_model=List[Pozo],
    summary="Listado de pozos (datos reales de gold)",
    description="""
Lista los pozos del maestro con sus atributos reales de la capa gold.

**Filtros opcionales:** `provincia`, `cuenca`.
**Paginado:** `limit` (default 100, máx 1000) y `offset`.

**Errores posibles:**
- `403` si la API key es inválida o falta
- `429` si se supera el límite de 60 requests por minuto
- `503` si el data warehouse no está disponible
""",
)
@limiter.limit("60/minute")
def list_pozos(
    request: Request,
    provincia: Optional[str] = None,
    cuenca: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    x_api_key: str = Header(default=""),
) -> List[Pozo]:
    _validate_api_key(x_api_key)
    sql = _SELECT_POZO + """
        where (%(provincia)s::text is null or provincia = %(provincia)s::text)
          and (%(cuenca)s::text is null or cuenca = %(cuenca)s::text)
        order by idpozo
        limit %(limit)s offset %(offset)s
    """
    return _fetch(sql, {"provincia": provincia, "cuenca": cuenca, "limit": limit, "offset": offset})


@router.get(
    "/pozos/{idpozo}",
    response_model=Pozo,
    summary="Pozo por id (datos reales de gold)",
    description="""
Devuelve un pozo por su identificador.

**Errores posibles:**
- `403` si la API key es inválida o falta
- `404` si el pozo no existe
- `429` si se supera el límite de 60 requests por minuto
- `503` si el data warehouse no está disponible
""",
)
@limiter.limit("60/minute")
def get_pozo(
    request: Request,
    idpozo: str,
    x_api_key: str = Header(default=""),
) -> Pozo:
    _validate_api_key(x_api_key)
    sql = _SELECT_POZO + " where idpozo::text = %(idpozo)s limit 1"
    rows = _fetch(sql, {"idpozo": idpozo})
    if not rows:
        raise HTTPException(status_code=404, detail=f"El pozo {idpozo} no existe.")
    return rows[0]
