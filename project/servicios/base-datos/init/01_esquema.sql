-- Esquema inicial de la base de datos del proyecto.
-- Postgres ejecuta todo lo que haya en /docker-entrypoint-initdb.d/ una
-- única vez, la primera vez que el volumen de datos está vacío. Si cambiás
-- este archivo después de haber levantado la base una vez, no se vuelve a
-- correr solo con un restart: hay que borrar el volumen (ver README) o
-- aplicar el cambio a mano con una migración.

-- PostGIS: lo pide el equipo para las consultas espaciales sobre las
-- detecciones (lat/lon, cajas, exportación a GeoJSON). Si tu tabla no usa
-- geometría todavía, no pasa nada: la extensión queda instalada y lista
-- para cuando la necesiten.
CREATE EXTENSION IF NOT EXISTS postgis;

-- Usuarios de la aplicación (login real, issue #47).
-- Pensada para mostrar algo más que el username en el front: nombre
-- completo, rol y avatar (el de GitHub, ya que todos tienen cuenta) además
-- de cuándo se creó la cuenta y cuándo fue el último acceso.
CREATE TABLE IF NOT EXISTS usuarios (
    id              SERIAL PRIMARY KEY,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    nombre_completo TEXT NOT NULL,
    rol             TEXT NOT NULL DEFAULT 'colaborador',
    avatar_url      TEXT,
    fecha_alta      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_acceso   TIMESTAMPTZ
);

COMMENT ON TABLE usuarios IS 'Cuentas del equipo para el login de AgroVision.';
COMMENT ON COLUMN usuarios.rol IS 'admin | colaborador. Hoy solo se usa para mostrarlo en el front, no restringe nada todavía.';
