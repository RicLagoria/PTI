import os
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles

from predict import ejecutar_inspeccion_segmentada

app = FastAPI(title="AgroVision API - COG & Detections")

# Permitir peticiones desde tu frontend (React, Vite, HTML local, etc.)
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
    Lee en tiempo real únicamente los píxeles necesarios para el zoom Z y celda X/Y
    directamente desde la estructura interna del archivo COG.
    """
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    try:
        with Reader(tif_path) as cog:
            # Extrae la ventana exacta calculando la reproyección al vuelo a Web Mercator
            img = cog.tile(x, y, z, tilesize=256)
            # Renderiza a PNG de 8 bits
            contenido_png = img.render(img_format="PNG", **img_profiles.get("png"))
            
        return Response(content=contenido_png, media_type="image/png")
    except Exception as e:
        # Fuera de los límites del mapa o zoom no disponible
        raise HTTPException(status_code=404, detail=f"Tesela fuera de rango: {e}")

# ==========================================================
# 2. ENDPOINT: OBTENER BOUNDS/METADATOS DEL CAMPO
# ==========================================================
@app.get("/metadata")
def obtener_metadata(tif_path: str = RUTA_COG_DEFAULT):
    """Devuelve las coordenadas envolventes (bounds) para centrar el mapa en el front."""
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    with Reader(tif_path) as cog:
        bounds = cog.get_geographic_bounds(cog.crs)  # (minx, miny, maxx, maxy) -> (W, S, E, N)
        return {
            "bounds": [
                [bounds[1], bounds[0]], # Suroeste [lat, lon]
                [bounds[3], bounds[2]]  # Noreste [lat, lon]
            ],
            "minzoom": cog.minzoom,
            "maxzoom": cog.maxzoom
        }

# ==========================================================
# 3. ENDPOINT: INFERENCIA Y ENTREGA DEL JSON
# ==========================================================
@app.post("/analizar")
def analizar_campo(cuadrante: int = 3, conf: float = 0.10, tif_path: str = RUTA_COG_DEFAULT):
    """Ejecuta el pipeline modular de YOLOv8 y devuelve las detecciones en formato JSON."""
    if not os.path.exists(tif_path):
        raise HTTPException(status_code=404, detail="Archivo GeoTIFF no encontrado.")

    resultados = ejecutar_inspeccion_segmentada(
        ruta_tif=tif_path,
        cuadrante=cuadrante,
        ruta_json="detecciones_campo.json",
        conf=conf
    )
    return resultados