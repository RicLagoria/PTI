-- A qué escala corrió cada análisis.
--
-- Hasta acá una celda del recorrido era siempre `imgsz` píxeles del raster
-- leídos tal cual, que a 3,3 cm/px son unos 21 m: una mancha más grande no
-- entraba entera en la imagen y el modelo aprendía a cortarla. Con la escala,
-- una celda pasa a ser `imgsz * escala` píxeles reducidos a `imgsz`, o sea el
-- mismo encuadre con más campo. Ver py_geo.GeoHandler.
--
-- Hace falta guardarla porque dos análisis del mismo ortomosaico con el mismo
-- modelo y la misma confianza pueden dar resultados muy distintos solo por
-- esto, y sin la columna no habría manera de saber cuál fue cuál. Los análisis
-- anteriores corrieron todos a escala 1, que es lo que dice el DEFAULT.
--
-- Postgres corre los archivos de /docker-entrypoint-initdb.d una sola vez, al
-- crear el volumen. Sobre una base que ya existe hay que aplicarlo a mano:
--
--   docker compose -f despliegue/compose.dev.yml exec -T db \
--     psql -U agrovision -d agrovision < project/servicios/base-datos/init/04_escala.sql
--
-- Está escrito para que repetirlo no haga nada.

ALTER TABLE analisis
    ADD COLUMN IF NOT EXISTS escala INTEGER NOT NULL DEFAULT 1;

COMMENT ON COLUMN analisis.escala IS
    'Cuántas veces el lado de una celda del recorrido es más grande que la entrada del modelo. 1 es leer el raster a resolución nativa; 4 lee una celda de 4*imgsz px y la reduce a imgsz, cubriendo 16 veces más campo por celda. Ver py_geo.GeoHandler y app/analisis.py.';
