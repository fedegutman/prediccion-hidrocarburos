"""Tests de la configuración de conexión al warehouse (``app.db``).

Verifican una propiedad de seguridad: la dirección/credenciales del warehouse
se toman de la variable de entorno ``WAREHOUSE_DSN`` (no quedan hardcodeadas
para producción), con un default solo para desarrollo local.
"""

from app import db


def test_get_dsn_usa_default_sin_env(monkeypatch) -> None:
    """Sin ``WAREHOUSE_DSN`` seteada, usa el default local."""
    monkeypatch.delenv("WAREHOUSE_DSN", raising=False)
    assert db.get_dsn() == db.DEFAULT_DSN


def test_get_dsn_respeta_env_override(monkeypatch) -> None:
    """Con ``WAREHOUSE_DSN`` seteada, se usa esa (para contenedor/nube)."""
    custom = "postgresql://usuario:clave@db-interna:5432/oilgas"
    monkeypatch.setenv("WAREHOUSE_DSN", custom)
    assert db.get_dsn() == custom
