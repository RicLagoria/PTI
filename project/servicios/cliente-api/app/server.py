import json
import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import almacen
import auth
import datos
import reportes
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


def carpeta_imagen(imagen_id: str) -> Path:
    """Resuelve el id de la URL a la carpeta de la imagen (vía la tabla ortomosaicos) o corta con 404."""
    if not almacen.validar_id(imagen_id):
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    ruta_archivo = datos.obtener_ruta_archivo(imagen_id)
    if ruta_archivo is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return Path(ruta_archivo).parent


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
    Al terminar lo valida, lo convierte a COG si hace falta, y registra la
    metadata en la tabla ortomosaicos (el .tif en sí sigue solo en disco).
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

        meta = await run_in_threadpool(almacen.finalizar_subida, imagen_id, nombre)
        return datos.registrar_ortomosaico(
            id_=imagen_id,
            usuario_id=usuario["id"],
            nombre=nombre,
            ancho_px=meta["ancho_px"],
            alto_px=meta["alto_px"],
            bounds=meta["bounds"],
            minzoom=meta["minzoom"],
            maxzoom=meta["maxzoom"],
            ruta_archivo=meta["ruta_archivo"],
        )
    except almacen.ImagenInvalida as e:
        almacen.descartar(imagen_id)
        raise HTTPException(status_code=400, detail=str(e))
    except BaseException:
        almacen.descartar(imagen_id)
        raise


@app.get("/imagenes")
def listar_imagenes(usuario=Depends(auth.usuario_actual)):
    """Imágenes ya subidas por cualquiera del equipo (no son privadas por usuario)."""
    return datos.listar_ortomosaicos()


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
def obtener_metadata(imagen_id: str, usuario=Depends(auth.usuario_actual)):
    """Devuelve las coordenadas envolventes y dimensiones del ortomosaico."""
    meta = datos.obtener_ortomosaico(imagen_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return meta


# ==========================================================
# 4. STREAMING DE DETECCIONES (SSE)
# ==========================================================
@app.get("/imagenes/{imagen_id}/analizar-stream")
def analizar_campo_stream(
    imagen_id: str,
    cuadrante: Optional[int] = None,
    conf: float = 0.10,
    carpeta=Depends(carpeta_imagen),
    usuario=Depends(auth.usuario_actual),
):
    """
    Consume el generador de analisis.py y transmite cada bloque vía Server-Sent Events.
    Cada corrida queda guardada en la tabla analisis (no pisa la anterior).
    """
    def generador_eventos():
        try:
            for chunk in ejecutar_inspeccion_segmentada(
                ruta_tif=str(carpeta / almacen.NOMBRE_COG),
                ortomosaico_id=imagen_id,
                usuario_id=usuario["id"],
                cuadrante=cuadrante,
                conf=conf
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            # Si algo se corta a mitad de camino (ia-inferencia no responde, se
            # cae la base, etc.) mejor cerrar el stream prolijo: si dejamos que
            # la excepción se escape acá, el chunked transfer queda a medias y
            # el navegador lo ve como ERR_INCOMPLETE_CHUNKED_ENCODING en vez de
            # un cierre normal que el EventSource.onerror del front ya maneja.
            print(f"[ERROR] analizar-stream cortado: {e}")

    return StreamingResponse(generador_eventos(), media_type="text/event-stream")


# ==========================================================
# 5. MODO BATCH COMPLETO (FALLBACK)
# ==========================================================
@app.post("/imagenes/{imagen_id}/analizar")
def analizar_campo_completo(
    imagen_id: str,
    cuadrante: Optional[int] = None,
    conf: float = 0.10,
    carpeta=Depends(carpeta_imagen),
    usuario=Depends(auth.usuario_actual),
):
    """Conserva la ejecución tradicional acumulando todos los bloques antes de responder."""
    resultado_final = None
    for chunk in ejecutar_inspeccion_segmentada(
        ruta_tif=str(carpeta / almacen.NOMBRE_COG),
        ortomosaico_id=imagen_id,
        usuario_id=usuario["id"],
        cuadrante=cuadrante,
        conf=conf
    ):
        resultado_final = chunk

    return resultado_final


# ==========================================================
# 6. HISTORIAL DE ANÁLISIS
# ==========================================================
def _analisis_de_la_imagen(imagen_id: str, analisis_id: int) -> dict:
    """Trae un análisis puntual y valida que sea de la imagen de la URL."""
    fila = datos.obtener_analisis(analisis_id)
    if fila is None or fila["ortomosaico_id"] != imagen_id:
        raise HTTPException(status_code=404, detail="Análisis no encontrado.")
    return fila


@app.get("/imagenes/{imagen_id}/analisis")
def listar_historial_analisis(imagen_id: str, carpeta=Depends(carpeta_imagen), usuario=Depends(auth.usuario_actual)):
    """Todas las corridas anteriores sobre esta imagen, más reciente primero."""
    return datos.listar_analisis(imagen_id)


@app.get("/imagenes/{imagen_id}/analisis/{analisis_id}")
def obtener_analisis_pasado(imagen_id: str, analisis_id: int, usuario=Depends(auth.usuario_actual)):
    """Para volver a ver un análisis viejo sin tener que re-ejecutarlo."""
    fila = _analisis_de_la_imagen(imagen_id, analisis_id)
    return {**fila, "detecciones": datos.obtener_detecciones(analisis_id)}


@app.get("/imagenes/{imagen_id}/analisis/{analisis_id}/exportar.geojson")
def exportar_geojson(imagen_id: str, analisis_id: int, usuario=Depends(auth.usuario_actual)):
    _analisis_de_la_imagen(imagen_id, analisis_id)
    geojson = datos.exportar_geojson(analisis_id)
    return Response(
        content=json.dumps(geojson),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="analisis-{analisis_id}.geojson"'},
    )


@app.get("/imagenes/{imagen_id}/analisis/{analisis_id}/exportar.csv")
def exportar_csv(imagen_id: str, analisis_id: int, usuario=Depends(auth.usuario_actual)):
    _analisis_de_la_imagen(imagen_id, analisis_id)
    csv_texto = datos.exportar_csv(analisis_id)
    return Response(
        content=csv_texto,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="analisis-{analisis_id}.csv"'},
    )


@app.get("/imagenes/{imagen_id}/analisis/{analisis_id}/exportar.pdf")
def exportar_pdf(imagen_id: str, analisis_id: int, usuario=Depends(auth.usuario_actual)):
    """Informe visual: la imagen del campo con las detecciones marcadas, no solo datos crudos."""
    analisis = _analisis_de_la_imagen(imagen_id, analisis_id)
    ortomosaico = datos.obtener_ortomosaico(imagen_id)
    ruta_archivo = datos.obtener_ruta_archivo(imagen_id)
    if ortomosaico is None or ruta_archivo is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    detecciones = datos.obtener_detecciones(analisis_id)

    pdf_bytes = reportes.generar_pdf(
        ortomosaico={**ortomosaico, "ruta_archivo": ruta_archivo},
        analisis=analisis,
        detecciones=detecciones,
        usuario_nombre=analisis.get("usuario_nombre"),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="analisis-{analisis_id}.pdf"'},
    )


# ==========================================================
# 7. DASHBOARD
# ==========================================================
@app.get("/estadisticas")
def estadisticas(usuario=Depends(auth.usuario_actual)):
    """Los KPI reales del dashboard: cobertura, confianza del modelo, eficiencia del pipeline."""
    return datos.estadisticas_dashboard()
