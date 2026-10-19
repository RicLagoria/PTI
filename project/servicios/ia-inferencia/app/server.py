from typing import List, Optional
import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from detector import FieldDetector

app = FastAPI(title="AgroVision - Servicio de Inferencia IA", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/salud")
def salud():
    detector = FieldDetector()
    return {
        "estado": "ok",
        "modelo_cargado": detector.esta_disponible(),
        "ruta_modelo": detector.ruta_modelo
    }


@app.get("/modelo")
def info_modelo():
    detector = FieldDetector()
    return detector.obtener_info()


@app.post("/detectar")
async def detectar(
    request: Request,
    conf: float = Query(0.10, ge=0.0, le=1.0)
):
    """
    Recibe teselas en formato multipart.
    Cada archivo o campo lleva el 'id' de la celda como su nombre de campo o nombre de archivo.
    """
    form = await request.form()
    if not form:
        raise HTTPException(status_code=400, detail="No se recibieron teselas para procesar.")

    detector = FieldDetector()
    if not detector.esta_disponible():
        raise HTTPException(
            status_code=503,
            detail=f"Modelo no disponible en la ruta configurada: {detector.ruta_modelo}"
        )

    tiles_procesar = []
    for clave, valor in form.items():
        if isinstance(valor, UploadFile):
            contenido = await valor.read()
            # El id puede venir en el filename o en la clave del formulario
            tile_id = valor.filename or clave
        elif hasattr(valor, "read"):
            contenido = await valor.read()
            tile_id = clave
        elif isinstance(valor, bytes):
            contenido = valor
            tile_id = clave
        else:
            continue

        if not contenido:
            continue

        arr = np.frombuffer(contenido, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is not None:
            tiles_procesar.append((tile_id, img_bgr))

    if not tiles_procesar:
        raise HTTPException(status_code=400, detail="No se pudieron decodificar imágenes válidas.")

    detecciones = detector.procesar_lote(tiles_procesar, conf_threshold=conf)

    return {
        "version_modelo": detector.version,
        "total_teselas": len(tiles_procesar),
        "detecciones": detecciones
    }

