"""Configuración común de los tests.

Setea una API key de TEST en el entorno **antes** de que se importe la app, para
que la autenticación funcione en los tests sin depender de ningún valor real ni
hardcodear una clave de producción. Es un valor de prueba descartable.
"""

import os

os.environ.setdefault("API_KEY", "test-api-key")
