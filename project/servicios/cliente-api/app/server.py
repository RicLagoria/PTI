import json
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import almacen
import auth
from analisis import ejecutar_inspeccion_segmentada
from teselas import renderizar_tesela_png

app = FastAPI(title="AgroVision - Cliente API", version="1.0.0")

# Antes aceptaba cualquier origen ("*"); con login real de por medio eso ya
# no alcanza (las credenciales no pueden viajar a un origen comodín).
# FRONTEND_ORIGIN apunta a donde vive cliente-web; separar varios con coma.
_origenes = os.environ.get("FRONTEND_ORIGIN", "http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origenes if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CredencialesLogin(BaseModel):
    usuario: str
    contrasena: str


def carpeta_imagen(imagen_id: str):
    """Resuelve el id de la URL a la carpeta de la imagen o corta con 404."""
    carpeta = almacen.carpeta_de(imagen_id)
    if carpeta is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return carpeta


@app.get("/salud")
def salud():
    return {"estado": "ok", "servicio": "cliente-api"}


# ==========================================================
# 0. AUTENTICACIÓN (issue #47)
# ==========================================================
@app.post("/auth/login")
def iniciar_sesion(credenciales: CredencialesLogin):
    """Valida usuario/contraseña contra la base y devuelve un JWT + el perfil."""
    perfil = auth.autenticar(credenciales.usuario, credenciales.contrasena)
    return {"token": auth.crear_token(perfil), "perfil": perfil}


@app.get("/auth/yo")
def perfil_actual(usuario=Depends(auth.usuario_actual)):
    """El front lo usa para refrescar los datos del perfil sin loguear de nuevo."""
    return usuario


# ==========================================================
# 1. CARGA Y LISTADO DE ORTOMOSAICOS
# ==========================================================
@app.post("/imagenes", status_code=201)
async def subir_imagen(request: Request, nombre: str = "ortomosaico.tif", usuario=Depends(auth.usuario_actual)):
    """
    Recibe el GeoTIFF como cuerpo crudo de la petición y lo escribe a disco por partes.
    Al terminar lo valida y lo convierte a COG si hace falta.
    """
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
        almacen.descartar(imagen_id)
        raise


@app.get("/imagenes")
def listar_imagenes(usuario=Depends(auth.usuario_actual)):
    """Imágenes ya subidas."""
    return almacen.listar()


# ==========================================================
# 2. TESELAS DINÁMICAS (XYZ TILES)
# ==========================================================
@app.get("/imagenes/{imagen_id}/tiles/{z}/{x}/{y}.png")
def obtener_tesela(z: int, x: int, y: int, carpeta=Depends(carpeta_imagen), usuario=Depends(auth.usuario_actual)):
    """Lee bajo demanda los píxeles para el nivel de zoom Z y coords X/Y desde el COG."""
    try:
        ruta_cog = carpeta / almacen.NOMBRE_COG
        contenido_png = renderizar_tesela_png(ruta_cog, z, x, y)
        return Response(content=contenido_png, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Tesela fuera de rango: {e}")


# ==========================================================
# 3. METADATOS Y BOUNDS
# ==========================================================
@app.get("/imagenes/{imagen_id}/metadata")
def obtener_metadata(carpeta=Depends(carpeta_imagen), usuario=Depends(auth.usuario_actual)):
    """Devuelve las coordenadas envolventes y dimensiones del ortomosaico."""
    return almacen.leer_meta(carpeta)


# ==========================================================
# 4. STREAMING DE DETECCIONES (SSE)
# ==========================================================
@app.get("/imagenes/{imagen_id}/analizar-stream")
def analizar_campo_stream(
    cuadrante: Optional[int] = None,
    conf: float = 0.10,
    carpeta=Depends(carpeta_imagen),
    usuario=Depends(auth.usuario_actual),
):
    """
    Consume el generador de analisis.py y transmite cada bloque vía Server-Sent Events.
    """
    def generador_eventos():
        for chunk in ejecutar_inspeccion_segmentada(
            ruta_tif=str(carpeta / almacen.NOMBRE_COG),
            cuadrante=cuadrante,
            ruta_json=str(carpeta / almacen.NOMBRE_DETECCIONES),
            conf=conf
        ):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(generador_eventos(), media_type="text/event-stream")


# ==========================================================
# 5. MODO BATCH COMPLETO (FALLBACK)
# ==========================================================
@app.post("/imagenes/{imagen_id}/analizar")
def analizar_campo_completo(
    cuadrante: Optional[int] = None,
    conf: float = 0.10,
    carpeta=Depends(carpeta_imagen),
    usuario=Depends(auth.usuario_actual),
):
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
