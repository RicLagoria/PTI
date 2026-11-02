"""
Análisis en segundo plano: canal asíncrono de cliente-api (Entrega 3 de PDC).

`POST /imagenes/{id}/analisis` no espera al resultado: reserva el lock de la
imagen, deja un estado `en_curso` en disco, lanza un hilo y responde 202 en
milisegundos. El cliente consulta el avance con `GET /imagenes/{id}/analisis`
cuando quiere, sin tener una conexión abierta durante minutos (a diferencia del
stream SSE, que muere si se cae la conexión).

El estado vive en `analisis_estado.json` dentro de la carpeta de la imagen,
escrito de forma atómica. Es el mismo patrón que la cola de entrenamiento de
`ia-entrenamiento` (un JSON por trabajo en disco), así que no suma infraestructura.
"""
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import almacen
from analisis import ejecutar_inspeccion_segmentada
from bloqueo import BloqueoImagen, escribir_json_atomico, hay_analisis_activo

NOMBRE_ESTADO = "analisis_estado.json"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def leer_estado(carpeta: Path) -> Optional[dict]:
    """
    Último estado conocido del análisis de la imagen, o None si nunca se corrió.
    Si el archivo dice `en_curso` pero nadie tiene el lock, el proceso murió a
    mitad de camino: se informa `interrumpido` en vez de mentir.
    """
    ruta = Path(carpeta) / NOMBRE_ESTADO
    if not ruta.is_file():
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            estado = json.load(f)
    except (OSError, ValueError):
        return None
    if estado.get("estado") == "en_curso" and not hay_analisis_activo(carpeta):
        estado["estado"] = "interrumpido"
    return estado


def lanzar(carpeta: Path, bloqueo: BloqueoImagen, cuadrante: Optional[int], conf: float) -> dict:
    """
    Arranca el análisis en un hilo y devuelve el estado inicial. Quien llama ya
    tiene tomado el `bloqueo`; el hilo es quien lo suelta al terminar.
    """
    estado = {
        "id": uuid.uuid4().hex[:12],
        "estado": "en_curso",
        "cuadrante": cuadrante,
        "conf": conf,
        "inicio": _ahora(),
        "fin": None,
        "progreso_pct": 0.0,
        "detecciones_acumuladas": 0,
        "error": None,
    }
    escribir_json_atomico(Path(carpeta) / NOMBRE_ESTADO, estado)
    threading.Thread(
        target=_ejecutar, args=(Path(carpeta), bloqueo, estado, cuadrante, conf), daemon=True
    ).start()
    return dict(estado)


def _ejecutar(carpeta: Path, bloqueo: BloqueoImagen, estado: dict, cuadrante: Optional[int], conf: float):
    ruta_estado = carpeta / NOMBRE_ESTADO
    try:
        for chunk in ejecutar_inspeccion_segmentada(
            ruta_tif=str(carpeta / almacen.NOMBRE_COG),
            cuadrante=cuadrante,
            ruta_json=str(carpeta / almacen.NOMBRE_DETECCIONES),
            conf=conf,
        ):
            estado["progreso_pct"] = chunk["progreso_pct"]
            estado["detecciones_acumuladas"] = chunk["total_acumuladas"]
            escribir_json_atomico(ruta_estado, estado)
        estado["estado"] = "completado"
        estado["progreso_pct"] = 100.0
    except Exception as e:
        estado["estado"] = "fallido"
        estado["error"] = str(e)
    finally:
        estado["fin"] = _ahora()
        try:
            escribir_json_atomico(ruta_estado, estado)
        finally:
            bloqueo.liberar()
