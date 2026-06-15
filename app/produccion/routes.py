"""Rutas de solo lectura para la producción mensual (``gold.fct_produccion``).

Exponen el hecho de producción del modelo estrella, enriquecido con los
atributos descriptivos de las dimensiones (empresa operadora, geografía).
Es de solo lectura: la API nunca modifica el warehouse.
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


class ProduccionRecord(BaseModel):
    """Registro de producción mensual de un pozo (grano: pozo x mes).

    :param idpozo: Identificador del pozo.
    :param anio: Año del período.
    :param mes: Mes del período (1-12).
    :param fecha_mes: Primer día del mes del período (``YYYY-MM-DD``).
    :param empresa: Empresa operadora ese mes.
    :param cuenca: Cuenca.
    :param provincia: Provincia.
    :param area_yacimiento: Área o yacimiento.
    :param prod_pet: Producción de petróleo.
    :param prod_gas: Producción de gas.
    :param prod_agua: Producción de agua.
    """

    idpozo: str
    anio: int
    mes: int
    fecha_mes: str
    empresa: Optional[str] = None
    cuenca: Optional[str] = None
    provincia: Optional[str] = None
    area_yacimiento: Optional[str] = None
    prod_pet: Optional[float] = None
    prod_gas: Optional[float] = None
    prod_agua: Optional[float] = None


_SELECT_PRODUCCION = """
    select
        f.idpozo::text                     as idpozo,
        f.anio,
        f.mes,
        to_char(f.fecha_mes, 'YYYY-MM-DD')  as fecha_mes,
        e.empresa,
        a.cuenca,
        a.provincia,
        a.area_yacimiento,
        f.prod_pet,
        f.prod_gas,
        f.prod_agua
    from gold.fct_produccion f
    left join gold.dim_empresa e on e.empresa_sk = f.empresa_sk
    left join gold.dim_area    a on a.area_sk    = f.area_sk
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
    "/produccion",
    response_model=List[ProduccionRecord],
    summary="Producción mensual real (gold)",
    description="""
Devuelve la producción mensual por pozo desde el modelo estrella
(`gold.fct_produccion`), enriquecida con empresa operadora y geografía.

**Filtros opcionales:** `idpozo`, `anio`.
**Paginado:** `limit` (default 100, máx 1000) y `offset`.

**Errores posibles:**
- `403` si la API key es inválida o falta
- `429` si se supera el límite de 60 requests por minuto
- `503` si el data warehouse no está disponible
""",
)
@limiter.limit("60/minute")
def list_produccion(
    request: Request,
    idpozo: Optional[str] = None,
    anio: Optional[int] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    x_api_key: str = Header(default=""),
) -> List[ProduccionRecord]:
    _validate_api_key(x_api_key)
    sql = _SELECT_PRODUCCION + """
        where (%(idpozo)s::text is null or f.idpozo::text = %(idpozo)s::text)
          and (%(anio)s::int is null or f.anio = %(anio)s::int)
        order by f.fecha_mes desc, f.idpozo
        limit %(limit)s offset %(offset)s
    """
    return _fetch(sql, {"idpozo": idpozo, "anio": anio, "limit": limit, "offset": offset})
