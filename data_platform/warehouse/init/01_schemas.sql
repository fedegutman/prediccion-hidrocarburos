-- Crea los tres schemas de la arquitectura medallion en el warehouse.
-- Se ejecuta automáticamente la primera vez que arranca el contenedor `warehouse`.

CREATE SCHEMA IF NOT EXISTS bronze;   -- dato crudo, tal cual viene de la fuente
CREATE SCHEMA IF NOT EXISTS silver;   -- dato limpio, tipado, deduplicado
CREATE SCHEMA IF NOT EXISTS gold;     -- modelo estrella, listo para negocio
