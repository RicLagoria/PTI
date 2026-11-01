-- Un análisis puede recorrer el campo varias veces, a escalas distintas.
--
-- La idea es la de alejarse y acercarse: una pasada gruesa (celdas de 4*imgsz
-- px reducidas a imgsz) ve manchas grandes que a resolución nativa no entran
-- enteras en la imagen, y una pasada fina ve las chicas y las escondidas entre
-- la caña. Ver py_geo.GeoHandler y app/analisis.py.
--
-- Por eso `analisis.escala` (04_escala.sql) pasa a ser `analisis.escalas`, la
-- lista de pasadas que corrieron y en qué orden, y cada detección guarda de qué
-- pasada salió. Lo segundo no es decorativo: la fusión de piezas y la supresión
-- de anidadas comparan detecciones entre sí, y comparar las de dos escalas
-- distintas no significa lo mismo. La fila/col de una detección son índices de
-- la grilla de *su* escala, y una mancha grande de la pasada gruesa contiene
-- por diseño a las chicas de la pasada fina, que son justamente el detalle que
-- la cascada quiere conservar.
--
-- Postgres corre los archivos de /docker-entrypoint-initdb.d una sola vez, al
-- crear el volumen. Sobre una base que ya existe hay que aplicarlo a mano:
--
--   docker compose -f despliegue/compose.dev.yml exec -T db \
--     psql -U agrovision -d agrovision < project/servicios/base-datos/init/05_cascada.sql
--
-- Está escrito para que repetirlo no haga nada.

ALTER TABLE analisis
    ADD COLUMN IF NOT EXISTS escalas INTEGER[] NOT NULL DEFAULT ARRAY[1];

-- Los análisis que corrieron con la columna anterior conservan su escala
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'analisis' AND column_name = 'escala'
    ) THEN
        EXECUTE 'UPDATE analisis SET escalas = ARRAY[escala] WHERE escalas = ARRAY[1]';
        EXECUTE 'ALTER TABLE analisis DROP COLUMN escala';
    END IF;
END
$$;

ALTER TABLE detecciones
    ADD COLUMN IF NOT EXISTS escala INTEGER NOT NULL DEFAULT 1;

COMMENT ON COLUMN analisis.escalas IS
    'Las pasadas que recorrieron el campo, en orden. [1] es el recorrido a resolución nativa de siempre; [4,1] primero se aleja para ver las manchas grandes enteras y después se acerca para las chicas.';
COMMENT ON COLUMN detecciones.escala IS
    'De qué pasada salió. La fusión de piezas y la supresión de anidadas solo comparan detecciones de la misma escala: entre escalas distintas, que una contenga a otra es lo esperado y no un duplicado.';

-- Las dos operaciones de post-proceso filtran por escala dentro de un análisis
CREATE INDEX IF NOT EXISTS detecciones_analisis_escala_idx
    ON detecciones (analisis_id, escala);
