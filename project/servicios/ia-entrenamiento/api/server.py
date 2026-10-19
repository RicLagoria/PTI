import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# Permitir importar desde nucleo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nucleo"))

import clases
import datasets
import registro
import trabajos

app = FastAPI(title="AgroVision - IA Entrenamiento API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SolicitudEntrenamiento(BaseModel):
    datasets: List[str]
    epocas: int = 50
    imgsz: int = 640
    pesos_base: str = "yolov8n.pt"


@app.get("/salud")
def salud():
    return {"estado": "ok", "servicio": "ia-entrenamiento-api"}


@app.get("/clases")
def listar_clases():
    """Retorna la taxonomía canónica de clases."""
    return clases.obtener_clases_canonicas()


@app.get("/datasets")
def listar_datasets():
    return datasets.listar_datasets()


@app.post("/datasets", status_code=201)
async def subir_dataset(archivo: UploadFile = File(...)):
    if not archivo.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="El dataset debe ser un archivo ZIP.")

    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="Archivo vacío.")

    try:
        meta = datasets.guardar_dataset_zip(contenido, archivo.filename)
        return meta
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando dataset: {e}")


@app.delete("/datasets/{id}", status_code=204)
def eliminar_dataset(id: str):
    if not datasets.eliminar_dataset(id):
        raise HTTPException(status_code=404, detail="Dataset no encontrado.")
    return Response(status_code=204)


@app.get("/entrenamientos")
def listar_entrenamientos():
    return trabajos.listar_trabajos()


@app.post("/entrenamientos", status_code=202)
def crear_entrenamiento(solicitud: SolicitudEntrenamiento):
    trabajo = trabajos.encolar_trabajo(
        datasets=solicitud.datasets,
        epocas=solicitud.epocas,
        imgsz=solicitud.imgsz,
        pesos_base=solicitud.pesos_base
    )
    return trabajo


@app.get("/entrenamientos/{id}/stream")
async def stream_entrenamiento(id: str):
    trabajo = trabajos.obtener_trabajo(id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo de entrenamiento no encontrado.")

    async def generador_stream():
        while True:
            t = trabajos.obtener_trabajo(id)
            if not t:
                break

            yield f"data: {json.dumps(t)}\n\n"

            if t["estado"] in ("completado", "fallido"):
                break

            await asyncio.sleep(2)

    return StreamingResponse(generador_stream(), media_type="text/event-stream")


@app.get("/modelos")
def listar_modelos():
    return registro.listar_modelos()


@app.get("/modelos/activo/pesos")
def descargar_pesos_activos():
    ruta = registro.ruta_pesos_activos()
    if not ruta or not ruta.is_file():
        raise HTTPException(status_code=404, detail="No hay pesos de modelo activo disponibles.")
    return FileResponse(
        path=str(ruta),
        media_type="application/octet-stream",
        filename="best.pt"
    )


@app.post("/modelos/{v}/activar")
def activar_modelo(v: str):
    exito = registro.activar_modelo(v)
    if not exito:
        raise HTTPException(status_code=404, detail=f"No se encontró la versión {v} o no tiene pesos válidos.")
    return {"mensaje": f"Modelo {v} activado correctamente."}

