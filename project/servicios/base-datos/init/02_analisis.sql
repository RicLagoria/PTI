-- Ortomosaicos, corridas de análisis y detecciones.
--
-- Reemplaza lo que hoy vive como archivos sueltos en
-- datos/ortomosaicos/<id>/ (meta.json y detecciones.json): el .tif pesado
-- sigue en disco tal cual, acá solo va lo que hoy ya se guardaba en esos
-- dos JSON, para que se pueda consultar con SQL en vez de parsearlo.
--
-- Ver el análisis completo (diagrama, justificación campo por campo) en
-- https://claude.ai/artifact/5s7BqxgAx6pa9FNg2KpauG

-- ==========================================================
-- Ortomosaicos — una fila por foto subida. Reemplaza meta.json.
-- ==========================================================
CREATE TABLE IF NOT EXISTS ortomosaicos (
    id              TEXT PRIMARY KEY CHECK (id ~ '^[0-9a-f]{32}$'),
    usuario_id      INTEGER REFERENCES usuarios(id),
    nombre          TEXT NOT NULL,
    fecha_subida    TIMESTAMPTZ NOT NULL DEFAULT now(),
    ancho_px        INTEGER NOT NULL,
    alto_px         INTEGER NOT NULL,
    bounds          GEOMETRY(POLYGON, 4326) NOT NULL,
    minzoom         INTEGER NOT NULL,
    maxzoom         INTEGER NOT NULL,
    ruta_archivo    TEXT NOT NULL
);

COMMENT ON TABLE ortomosaicos IS 'Un ortomosaico subido. El .tif sigue en disco (ruta_archivo apunta a él); acá va solo lo consultable.';
COMMENT ON COLUMN ortomosaicos.id IS 'Mismo id hex (32 chars, sin guiones) que hoy nombra la carpeta en datos/ortomosaicos/ — por eso es TEXT y no UUID, para no tener que convertir el formato en el código.';
COMMENT ON COLUMN ortomosaicos.bounds IS 'Rectángulo que ocupa la imagen en el mapa real (WGS84). Reemplaza el array [[sur,oeste],[norte,este]] de meta.json.';

CREATE INDEX IF NOT EXISTS ortomosaicos_bounds_idx ON ortomosaicos USING GIST (bounds);

-- ==========================================================
-- Análisis — una fila por cada corrida de análisis. No existía como
-- entidad propia: hoy volver a analizar pisaba detecciones.json entero.
-- ==========================================================
CREATE TABLE IF NOT EXISTS analisis (
    id                SERIAL PRIMARY KEY,
    ortomosaico_id    TEXT NOT NULL REFERENCES ortomosaicos(id) ON DELETE CASCADE,
    usuario_id        INTEGER REFERENCES usuarios(id),
    version_modelo    TEXT NOT NULL,
    conf_umbral       REAL NOT NULL,
    cuadrante         INTEGER,
    fecha_inicio      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_fin         TIMESTAMPTZ,
    total_celdas      INTEGER,
    celdas_activas    INTEGER,
    estado            TEXT NOT NULL DEFAULT 'en_progreso'
);

COMMENT ON TABLE analisis IS 'Una corrida de análisis sobre un ortomosaico. Cada corrida nueva es una fila nueva, nunca se pisa una existente.';
COMMENT ON COLUMN analisis.version_modelo IS 'Viene de GET /modelo en ia-inferencia. Permite comparar resultados entre versiones del modelo (ej. el que entrena Jorge vs. el actual).';
COMMENT ON COLUMN analisis.cuadrante IS 'NULL si se analizó la imagen completa.';
COMMENT ON COLUMN analisis.estado IS 'en_progreso | completo | error.';

CREATE INDEX IF NOT EXISTS analisis_ortomosaico_idx ON analisis (ortomosaico_id);

-- ==========================================================
-- Detecciones — una fila por cada maleza (u otra clase) detectada.
-- Reemplaza el array "detecciones" que hoy vive adentro de detecciones.json.
-- ==========================================================
CREATE TABLE IF NOT EXISTS detecciones (
    id              SERIAL PRIMARY KEY,
    analisis_id     INTEGER NOT NULL REFERENCES analisis(id) ON DELETE CASCADE,
    clase           TEXT NOT NULL,
    confianza       REAL NOT NULL,
    ubicacion       GEOMETRY(POINT, 4326) NOT NULL,
    box_global_px   INTEGER[] NOT NULL,
    fila            INTEGER NOT NULL,
    col             INTEGER NOT NULL
);

COMMENT ON TABLE detecciones IS 'Una detección individual dentro de un análisis.';
COMMENT ON COLUMN detecciones.clase IS 'Texto libre a propósito: la lista oficial de clases vive en contratos/clases.json (compartida con ia-inferencia/ia-entrenamiento, el orden ahí es el índice de YOLO). Duplicarla en una tabla aparte la desincroniza.';
COMMENT ON COLUMN detecciones.ubicacion IS 'Punto (no rectángulo) donde se encontró la detección. Reemplaza gps_centro {lat, lon}.';
COMMENT ON COLUMN detecciones.box_global_px IS 'Caja en píxeles globales [x1, y1, x2, y2], para volver a dibujar el marcador sin reprocesar la imagen.';

CREATE INDEX IF NOT EXISTS detecciones_analisis_idx ON detecciones (analisis_id);
CREATE INDEX IF NOT EXISTS detecciones_ubicacion_idx ON detecciones USING GIST (ubicacion);
