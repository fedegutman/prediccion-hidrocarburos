"""Acceso de solo lectura al data warehouse (capa gold).

La API consume ``gold`` como un *Data API*: lee la fuente autoritativa y NO
reimplementa lógica de negocio (las cuentas/agregaciones viven en gold/dbt),
de modo que la API y el BI muestren siempre los mismos números (evita la
"fragmentación de métricas" del semantic layer).

La dirección del warehouse se toma de la variable de entorno ``WAREHOUSE_DSN``
para poder cambiarla entre entornos (local / contenedor / nube) sin tocar el
código. El default apunta al warehouse local del ``data_platform``, expuesto en
el host en el puerto 5433.

Las consultas usan un **pool de conexiones** (``psycopg_pool``) inicializado en
el lifespan de la app (ver ``app/main.py``): reusar conexiones evita abrir/cerrar
una por request contra un warehouse con ``max_connections`` acotado. Si el pool
no está inicializado (p. ej. tests sin lifespan), ``run_query`` cae a una
conexión directa (fallback), preservando el comportamiento anterior.
"""

import os
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

# Default = warehouse local del data_platform (solo para desarrollo).
# En contenedor/producción se sobreescribe con WAREHOUSE_DSN.
DEFAULT_DSN = "postgresql://dwh:dwh@localhost:5433/oilgas"

# Pool global. Lo inicializa el lifespan de la app con init_pool() y lo cierra
# con close_pool(). Mientras sea None, run_query usa una conexión directa.
_pool: Optional[ConnectionPool] = None


def get_dsn() -> str:
    """Devuelve el connection string del warehouse.

    :return: Valor de ``WAREHOUSE_DSN`` o el default local si no está seteada.
    """
    return os.getenv("WAREHOUSE_DSN", DEFAULT_DSN)


def init_pool() -> None:
    """Crea y abre el pool de conexiones (idempotente). Lo llama el lifespan al arrancar.

    Se abre con ``wait=False``: NO bloquea el arranque si el warehouse está caído;
    las conexiones se crean on-demand y, si no hay warehouse, el primer query
    devuelve 503 (vía la traducción de ``PoolTimeout`` en ``run_query``).
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_dsn(),
            min_size=1,
            max_size=10,                       # holgado bajo el max_connections=20 del warehouse
            timeout=5.0,                       # falla rápido si no hay conexión disponible
            kwargs={"row_factory": dict_row},
            open=False,
        )
        _pool.open(wait=False)


def close_pool() -> None:
    """Cierra el pool y lo deja en None (lo llama el lifespan al apagar)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _run_direct(sql: str, params: Optional[Any]) -> List[Dict[str, Any]]:
    """Fallback sin pool: abre una conexión directa por consulta.

    Se usa cuando el pool no fue inicializado (tests sin lifespan, o un import
    suelto), preservando el comportamiento original.
    """
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def run_query(sql: str, params: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Ejecuta una consulta de solo lectura y devuelve las filas como dicts.

    Usa el pool si está inicializado; si no, cae a una conexión directa.

    :param sql: Sentencia SQL parametrizada (placeholders ``%s`` o ``%(nombre)s``).
    :param params: Valores de los parámetros (tupla o dict). Nunca interpolar a mano.
    :return: Lista de filas, cada una como diccionario columna -> valor.
    :raises psycopg.OperationalError: Si no se puede conectar al warehouse (incluido
        el timeout del pool, que se traduce a OperationalError para que la capa de
        rutas lo mapee a 503 como siempre).
    """
    if _pool is None:
        return _run_direct(sql, params)
    try:
        with _pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
    except PoolTimeout as exc:
        # El pool no consiguió conexión (warehouse caído o saturado): se traduce a
        # OperationalError para conservar el manejo de 503 de las rutas.
        raise psycopg.OperationalError("warehouse no disponible (pool timeout)") from exc
