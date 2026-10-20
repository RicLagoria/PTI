import asyncio
import json
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

# Permitir importar desde nucleo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nucleo"))

import clases
import datasets
import registro
import trabajos
from conversion_labelme import ErrorAporte

MAX_DATASET_MB = int(os.environ.get("MAX_DATASET_MB", "2048"))

# Corrida que se publica como primera versión si el registro está vacío
SEMILLA_DIR = Path(os.environ.get(
    "MODELO_SEMILLA_DIR",
    Path(__file__).resolve().parent.parent / "semilla" / "train-3",
))


@asynccontextmanager
async def lifespan(app: FastAPI):
    version = registro.sembrar_si_vacio(SEMILLA_DIR, clases.obtener_clases_canonicas())
    if version:
        print(f"[REGISTRO] Registro vacío: se publicó y activó la semilla {version}.")
    yield


app = FastAPI(title="AgroVision - IA Entrenamiento API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SolicitudEntrenamiento(BaseModel):
    datasets: List[str] = Field(..., min_length=1)
    epocas: int = Field(50, ge=1, le=300)
    imgsz: int = Field(640, ge=320, le=1280, multiple_of=32)
    pesos_base: str = "yolov8n.pt"
    # Parte de cada aporte que se separa para validar (y para la evaluación final)
    fraccion_validacion: float = Field(0.25, ge=0.1, le=0.5)


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


# Sin async: la conversión lee y escribe cada imagen, y en un endpoint async
# bloquearía el event loop (y con él los streams de entrenamiento) mientras dura.
@app.post("/datasets", status_code=201)
def subir_dataset(archivo: UploadFile = File(...), nombre: Optional[str] = Form(None)):
    if not (archivo.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="El dataset debe ser un archivo ZIP.")

    nombre_final = (nombre or "").strip() or Path(archivo.filename).stem
    maximo = MAX_DATASET_MB * 1024 * 1024

    # Se copia a un archivo temporal propio, por partes y sin cargarlo en memoria.
    # No alcanza con pasarle archivo.file a zipfile: en Python 3.9 el
    # SpooledTemporaryFile de Starlette no tiene seekable() y zipfile lo exige.
    datasets.DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=datasets.DATASETS_DIR) as copia:
        tamano = 0
        while True:
            parte = archivo.file.read(1024 * 1024)
            if not parte:
                break
            tamano += len(parte)
            if tamano > maximo:
                raise HTTPException(status_code=413, detail=f"El ZIP supera el máximo de {MAX_DATASET_MB} MB.")
            copia.write(parte)
        if tamano == 0:
            raise HTTPException(status_code=400, detail="Archivo vacío.")
        copia.seek(0)

        try:
            return datasets.guardar_dataset_zip(copia, nombre_final, archivo.filename)
        except ErrorAporte as e:
            raise HTTPException(status_code=400, detail=e.detalle)


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
    ids = list(dict.fromkeys(solicitud.datasets))
    inexistentes = [i for i in ids if datasets.carpeta_de(i) is None]
    if inexistentes:
        raise HTTPException(status_code=400, detail={
            "mensaje": "Hay datasets que no existen.",
            "datasets_inexistentes": inexistentes,
        })

    if registro.resolver_pesos_base(solicitud.pesos_base) is None:
        raise HTTPException(status_code=400, detail={
            "mensaje": f"Pesos de partida no permitidos: {solicitud.pesos_base}",
            "pesos_base_validos": list(registro.PESOS_BASE_OFICIALES) + [m["version"] for m in registro.listar_modelos()],
        })

    trabajo = trabajos.encolar_trabajo(
        datasets=ids,
        epocas=solicitud.epocas,
        imgsz=solicitud.imgsz,
        pesos_base=solicitud.pesos_base,
        fraccion_validacion=solicitud.fraccion_validacion,
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


@app.get("/modelos/{v}/detalle")
def detalle_modelo(v: str):
    """Evaluación sobre validación, historial por época y gráficos disponibles."""
    detalle = registro.leer_detalle(v)
    if detalle is None:
        raise HTTPException(status_code=404, detail=f"No se encontró la versión {v}.")
    return detalle


@app.get("/modelos/{v}/imagenes/{nombre}")
def imagen_modelo(v: str, nombre: str):
    ruta = registro.ruta_imagen(v, nombre)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return FileResponse(path=str(ruta), media_type="image/png")


@app.post("/modelos/{v}/activar")
def activar_modelo(v: str):
    exito = registro.activar_modelo(v)
    if not exito:
        raise HTTPException(status_code=404, detail=f"No se encontró la versión {v} o no tiene pesos válidos.")
    return {"mensaje": f"Modelo {v} activado correctamente."}
