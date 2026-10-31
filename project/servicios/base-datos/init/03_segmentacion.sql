-- Contorno de cada detección: lo que aporta un modelo de segmentación por
-- encima de uno de detección. Antes de esto una detección era un punto (el
-- centro de su caja) y el mapa solo podía marcarla; con el contorno se puede
-- dibujar el borde de la mancha de maleza y medir su superficie.
--
-- Las columnas se agregan en vez de rehacer "detecciones" porque las dos cosas
-- conviven: el modelo activo puede ser detect (la semilla train-3 lo es) y
-- entonces no hay contorno, y los análisis viejos tampoco lo tienen. Por eso
-- son NULL-ables y nada las exige.
--
-- Postgres corre los archivos de /docker-entrypoint-initdb.d una sola vez, al
-- crear el volumen. Sobre una base que ya existe hay que aplicarlo a mano:
--
--   docker compose -f despliegue/compose.dev.yml exec -T db \
--     psql -U agrovision -d agrovision < project/servicios/base-datos/init/03_segmentacion.sql
--
-- Está escrito para que repetirlo no haga nada (IF NOT EXISTS en todo).

ALTER TABLE detecciones
    ADD COLUMN IF NOT EXISTS contorno GEOMETRY(MULTIPOLYGON, 4326),
    ADD COLUMN IF NOT EXISTS contorno_global_px INTEGER[];

COMMENT ON COLUMN detecciones.contorno IS
    'Borde de la mancha detectada en WGS84, o NULL si el análisis corrió con un modelo de detección. MULTIPOLYGON y no POLYGON porque una máscara con el borde cruzado deja de ser un anillo simple y ST_MakeValid la parte en varios; ver datos.insertar_detecciones.';
COMMENT ON COLUMN detecciones.contorno_global_px IS
    'El mismo contorno en píxeles del ortomosaico, plano: [x1, y1, x2, y2, ...]. Es para el informe en PDF, que dibuja sobre la imagen y no sobre un mapa. Plano porque los arrays de Postgres son rectangulares y los contornos tienen distinta cantidad de vértices.';

-- Para "qué detecciones caen en este lote", que es una consulta por área y no
-- por análisis. El índice de detecciones_ubicacion_idx cubre el punto; este, la
-- superficie.
CREATE INDEX IF NOT EXISTS detecciones_contorno_idx ON detecciones USING GIST (contorno);
