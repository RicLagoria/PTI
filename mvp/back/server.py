import json
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles

import almacen
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


def carpeta_imagen(imagen_id: str):
    """Resuelve el id de la URL a la carpeta de la imagen o corta con 404."""
    carpeta = almacen.carpeta_de(imagen_id)
    if carpeta is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return carpeta

# ==========================================================
# 1. ENDPOINT: CARGA DE ORTOMOSAICOS
# ==========================================================
@app.post("/imagenes", status_code=201)
async def subir_imagen(request: Request, nombre: str = "ortomosaico.tif"):
    """
    Recibe el GeoTIFF como cuerpo crudo de la petición y lo escribe a disco por partes,
    sin cargarlo en memoria. Al terminar lo valida y lo convierte a COG si hace falta.
    """
    # El nombre solo se guarda para mostrarlo; en disco el archivo se identifica por id
    nombre = nombre.replace("\\", "/").split("/")[-1][:200]
    if not nombre.lower().endswith(almacen.EXTENSIONES_VALIDAS):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .tif o .tiff.")

    limite_mb = almacen.MAX_UPLOAD_BYTES // (1024 * 1024)
    error_tamano = HTTPException(status_code=413, detail=f"El archivo supera el máximo de {limite_mb} MB.")
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > almacen.MAX_UPLOAD_BYTES:
        raise error_tamano

    imagen_id, ruta_cruda = almacen.crear_carpeta_nueva()
    try:
        recibidos = 0
        with open(ruta_cruda, "wb") as f:
            async for parte in request.stream():
                recibidos += len(parte)
                if recibidos > almacen.MAX_UPLOAD_BYTES:
                    raise error_tamano
                f.write(parte)
        if recibidos == 0:
            raise HTTPException(status_code=400, detail="No se recibió ningún archivo.")

        return await run_in_threadpool(almacen.finalizar_subida, imagen_id, nombre)
    except almacen.ImagenInvalida as e:
        almacen.descartar(imagen_id)
        raise HTTPException(status_code=400, detail=str(e))
    except BaseException:
        # Incluye la desconexión del cliente a mitad de la subida: no dejar restos en disco
        almacen.descartar(imagen_id)
        raise

@app.get("/imagenes")
def listar_imagenes():
    """Imágenes ya subidas, para retomarlas sin volver a cargarlas."""
    return almacen.listar()

# ==========================================================
# 2. ENDPOINT: SERVIDOR DE TESELAS DINÁMICAS (XYZ TILES)
# ==========================================================
@app.get("/imagenes/{imagen_id}/tiles/{z}/{x}/{y}.png")
def obtener_tesela(z: int, x: int, y: int, carpeta=Depends(carpeta_imagen)):
    """
    Lee bajo demanda únicamente los píxeles necesarios para el nivel de zoom Z
    y coordenadas X/Y directamente desde la estructura COG.
    """
    try:
        with Reader(str(carpeta / almacen.NOMBRE_COG)) as cog:
            img = cog.tile(x, y, z, tilesize=256)
            contenido_png = img.render(img_format="PNG", **img_profiles.get("png"))

        return Response(content=contenido_png, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Tesela fuera de rango: {e}")

# ==========================================================
# 3. ENDPOINT: METADATOS Y BOUNDS DEL CAMPO
# ==========================================================
@app.get("/imagenes/{imagen_id}/metadata")
def obtener_metadata(carpeta=Depends(carpeta_imagen)):
    """Devuelve las coordenadas envolventes para encuadrar la cámara del visor."""
    return almacen.leer_meta(carpeta)

# ==========================================================
# 4. ENDPOINT: STREAMING DE DETECCIONES EN TIEMPO REAL (SSE)
# ==========================================================
@app.get("/imagenes/{imagen_id}/analizar-stream")
def analizar_campo_stream(cuadrante: Optional[int] = None, conf: float = 0.10, carpeta=Depends(carpeta_imagen)):
    """
    Consume el generador de predict.py y transmite cada bloque del 10%
    al frontend conforme YOLOv8 completa la inferencia.
    Sin cuadrante (o fuera de 1-4) se analiza la imagen completa.
    """
    def generador_eventos():
        for chunk in ejecutar_inspeccion_segmentada(
            ruta_tif=str(carpeta / almacen.NOMBRE_COG),
            cuadrante=cuadrante,
            ruta_json=str(carpeta / almacen.NOMBRE_DETECCIONES),
            conf=conf
        ):
            # Estructura requerida por el estándar Server-Sent Events (SSE)
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(generador_eventos(), media_type="text/event-stream")

# ==========================================================
# 5. ENDPOINT: MODO BATCH COMPLETO (FALLBACK)
# ==========================================================
@app.post("/imagenes/{imagen_id}/analizar")
def analizar_campo_completo(cuadrante: Optional[int] = None, conf: float = 0.10, carpeta=Depends(carpeta_imagen)):
    """Conserva la ejecución tradicional acumulando todos los bloques antes de responder."""
    resultado_final = None
    for chunk in ejecutar_inspeccion_segmentada(
        ruta_tif=str(carpeta / almacen.NOMBRE_COG),
        cuadrante=cuadrante,
        ruta_json=str(carpeta / almacen.NOMBRE_DETECCIONES),
        conf=conf
    ):
        resultado_final = chunk

    return resultado_final
