"""Acceso de solo lectura al data warehouse (capa gold).

La API consume ``gold`` como un *Data API*: lee la fuente autoritativa y NO
reimplementa lógica de negocio (las cuentas/agregaciones viven en gold/dbt),
de modo que la API y el BI muestren siempre los mismos números (evita la
"fragmentación de métricas" del semantic layer).

La dirección del warehouse se toma de la variable de entorno ``WAREHOUSE_DSN``
para poder cambiarla entre entornos (local / contenedor / nube) sin tocar el
código. El default apunta al warehouse local del ``data_platform``, expuesto en
el host en el puerto 5433.
"""

import os
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

# Default = warehouse local del data_platform (solo para desarrollo).
# En contenedor/producción se sobreescribe con WAREHOUSE_DSN.
DEFAULT_DSN = "postgresql://dwh:dwh@localhost:5433/oilgas"


def get_dsn() -> str:
    """Devuelve el connection string del warehouse.

    :return: Valor de ``WAREHOUSE_DSN`` o el default local si no está seteada.
    """
    return os.getenv("WAREHOUSE_DSN", DEFAULT_DSN)


def run_query(sql: str, params: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Ejecuta una consulta de solo lectura y devuelve las filas como dicts.

    :param sql: Sentencia SQL parametrizada (placeholders ``%s`` o ``%(nombre)s``).
    :param params: Valores de los parámetros (tupla o dict). Nunca interpolar a mano.
    :return: Lista de filas, cada una como diccionario columna -> valor.
    :raises psycopg.OperationalError: Si no se puede conectar al warehouse.
    """
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
