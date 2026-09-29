import json
import os
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles

from predict import ejecutar_inspeccion_segmentada

app = FastAPI(title="AgroVision API - COG & Detections")

# Configuración CORS para peticiones desde el frontend web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUTA_COG_DEFAULT = "El Azul_COG.tif"

# ==========================================================
# 1. ENDPOINT: SERVIDOR DE TESELAS DINÁMICAS (XYZ TILES)
# ==========================================================
@app.get("/tiles/{z}/{x}/{y}.png")
def obtener_tesela(z: int, x: int, y: int, tif_path: str = RUTA_COG_DEFAULT):
    """
    Lee bajo demanda únicamente los píxeles necesarios para el nivel de zoom Z
    y coordenadas X/Y directamente desde la estructura COG.
    """
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    try:
        with Reader(tif_path) as cog:
            img = cog.tile(x, y, z, tilesize=256)
            contenido_png = img.render(img_format="PNG", **img_profiles.get("png"))
            
        return Response(content=contenido_png, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Tesela fuera de rango: {e}")

# ==========================================================
# 2. ENDPOINT: METADATOS Y BOUNDS DEL CAMPO
# ==========================================================
@app.get("/metadata")
def obtener_metadata(tif_path: str = RUTA_COG_DEFAULT):
    """Devuelve las coordenadas envolventes para encuadrar la cámara del visor."""
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    with Reader(tif_path) as cog:
        bounds = cog.get_geographic_bounds(cog.crs)  # (W, S, E, N)
        return {
            "bounds": [
                [bounds[1], bounds[0]],  # Suroeste [lat, lon]
                [bounds[3], bounds[2]]   # Noreste [lat, lon]
            ],
            "minzoom": cog.minzoom,
            "maxzoom": cog.maxzoom
        }

# ==========================================================
# 3. ENDPOINT: STREAMING DE DETECCIONES EN TIEMPO REAL (SSE)
# ==========================================================
@app.get("/analizar-stream")
def analizar_campo_stream(cuadrante: int = 3, conf: float = 0.10, tif_path: str = RUTA_COG_DEFAULT):
    """
    Consume el generador de predict.py y transmite cada bloque del 10% 
    al frontend conforme YOLOv8 completa la inferencia.
    """
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    def generador_eventos():
        for chunk in ejecutar_inspeccion_segmentada(
            ruta_tif=tif_path,
            cuadrante=cuadrante,
            ruta_json="detecciones_campo.json",
            conf=conf
        ):
            # Estructura requerida por el estándar Server-Sent Events (SSE)
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(generador_eventos(), media_type="text/event-stream")

# ==========================================================
# 4. ENDPOINT: MODO BATCH COMPLETO (FALLBACK)
# ==========================================================
@app.post("/analizar")
def analizar_campo_completo(cuadrante: int = 3, conf: float = 0.10, tif_path: str = RUTA_COG_DEFAULT):
    """Conserva la ejecución tradicional acumulando todos los bloques antes de responder."""
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    resultado_final = None
    for chunk in ejecutar_inspeccion_segmentada(
        ruta_tif=tif_path,
        cuadrante=cuadrante,
        ruta_json="detecciones_campo.json",
        conf=conf
    ):
        resultado_final = chunk

    return resultado_final