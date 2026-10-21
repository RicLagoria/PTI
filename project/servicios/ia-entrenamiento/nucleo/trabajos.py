import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _obtener_dir_trabajos() -> Path:
    env_dir = os.environ.get("TRABAJOS_DIR")
    if env_dir:
        return Path(env_dir)

    candidatos = [
        Path("datos/trabajos"),
        Path("../datos/trabajos"),
        Path("../../datos/trabajos"),
        Path("/data/trabajos"),
        Path("data/trabajos"),
    ]
    for c in candidatos:
        if c.is_dir():
            return c

    ruta = Path("datos/trabajos")
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


TRABAJOS_DIR = _obtener_dir_trabajos()

# El id viaja en las URLs y arma nombres de archivo (.json, .lock, .cancelar)
ID_VALIDO = re.compile(r"^[0-9a-f]{12}$")

ESTADOS_FINALES = ("completado", "fallido", "cancelado")

# Un trabajo en ejecución actualiza su "latido" al menos al cerrar cada fase y
# cada pocos segundos mientras entrena. Si pasa más que esto sin latido, se da
# por muerto al worker y la cancelación se aplica sin esperarlo.
LATIDO_MAXIMO_S = 600


def _archivo(trabajo_id: str, extension: str) -> Optional[Path]:
    if not ID_VALIDO.match(trabajo_id or ""):
        return None
    return TRABAJOS_DIR / f"{trabajo_id}.{extension}"


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cancelacion_pedida(trabajo_id: str) -> bool:
    """La señal de cancelación es un archivo aparte: el JSON del trabajo lo reescribe el worker."""
    marca = _archivo(trabajo_id, "cancelar")
    return marca is not None and marca.exists()


def _con_cancelacion(trabajo: Dict) -> Dict:
    if trabajo.get("estado") in ("pendiente", "ejecutando"):
        trabajo["cancelacion_pedida"] = cancelacion_pedida(trabajo.get("id", ""))
    return trabajo


def _escribir_json_atomico(ruta: Path, data: Dict) -> None:
    """
    Escribe el JSON en un temporal y lo renombra encima del original. El renombrado es
    atómico: quien lea el archivo (la API mandando el progreso, otro worker buscando
    pendientes) ve la versión anterior completa o la nueva completa, nunca una a medias.
    """
    temporal = ruta.with_name(f".{ruta.name}.{uuid.uuid4().hex}.tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    # En Windows el renombrado falla si otro proceso tiene el destino abierto en ese
    # instante; se reintenta. En Linux (Docker) reemplaza aunque esté abierto.
    for intento in range(50):
        try:
            os.replace(temporal, ruta)
            return
        except PermissionError:
            if intento == 49:
                raise
            time.sleep(0.01)


def encolar_trabajo(
    datasets: List[str],
    epocas: int = 50,
    imgsz: int = 640,
    pesos_base: str = "yolov8n.pt",
    fraccion_validacion: float = 0.25,
) -> Dict:
    TRABAJOS_DIR.mkdir(parents=True, exist_ok=True)
    trabajo_id = uuid.uuid4().hex[:12]
    archivo_trabajo = TRABAJOS_DIR / f"{trabajo_id}.json"

    trabajo = {
        "id": trabajo_id,
        "estado": "pendiente",  # pendiente, ejecutando, completado, fallido
        # Con microsegundos: es la clave de orden de la cola, y con precisión de segundos
        # varios trabajos encolados juntos empataban y se tomaba primero el más nuevo
        "fecha_creacion": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "datasets": datasets,
        "epocas": epocas,
        "imgsz": imgsz,
        "pesos_base": pesos_base,
        "fraccion_validacion": fraccion_validacion,
        "progreso_epocas": 0,
        "metricas": {},
        "version_generada": None,
        "error": None
    }

    _escribir_json_atomico(archivo_trabajo, trabajo)

    return trabajo


def listar_trabajos() -> List[Dict]:
    if not TRABAJOS_DIR.is_dir():
        return []

    res = []
    for f in sorted(TRABAJOS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as arch:
                res.append(_con_cancelacion(json.load(arch)))
        except Exception:
            pass
    return res


def obtener_trabajo(trabajo_id: str) -> Optional[Dict]:
    archivo = _archivo(trabajo_id, "json")
    if archivo is not None and archivo.is_file():
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                return _con_cancelacion(json.load(f))
        except Exception:
            pass
    return None


def actualizar_trabajo(trabajo_id: str, **kwargs) -> Optional[Dict]:
    archivo = _archivo(trabajo_id, "json")
    if archivo is None or not archivo.is_file():
        return None

    with open(archivo, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.update(kwargs)

    _escribir_json_atomico(archivo, data)

    return data


def obtener_siguiente_pendiente() -> Optional[Dict]:
    """
    Solo consulta: no reserva el trabajo. Con más de un worker, dos pueden recibir el
    mismo pendiente; para tomar un trabajo usar reclamar_siguiente_pendiente().
    """
    pendientes = [t for t in listar_trabajos() if t["estado"] == "pendiente"]
    if pendientes:
        # El más antiguo primero
        return sorted(pendientes, key=lambda x: x["fecha_creacion"])[0]
    return None


def reclamar_trabajo(trabajo_id: str, worker: str) -> bool:
    """
    Intenta quedarse con un trabajo creando su archivo .lock en modo exclusivo (O_EXCL):
    el sistema operativo garantiza que, si varios workers lo intentan a la vez, solo uno
    lo crea. Retorna True si este worker lo reclamó y False si ya era de otro.
    """
    lock = _archivo(trabajo_id, "lock")
    if lock is None:
        return False
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(worker)
    return True


def reclamar_siguiente_pendiente(worker: str) -> Optional[Dict]:
    """
    Toma el pendiente más antiguo que ningún otro worker haya reclamado y lo marca como
    "ejecutando". Reemplaza al par obtener_siguiente_pendiente() + actualizar_trabajo(),
    que dejaba una ventana en la que dos workers tomaban el mismo trabajo.
    """
    pendientes = [t for t in listar_trabajos() if t["estado"] == "pendiente"]
    for trabajo in sorted(pendientes, key=lambda x: x["fecha_creacion"]):
        if reclamar_trabajo(trabajo["id"], worker):
            return actualizar_trabajo(trabajo["id"], estado="ejecutando", worker=worker, latido=ahora_iso())
    return None


def pedir_cancelacion(trabajo_id: str) -> Optional[Dict]:
    """
    Cancela un trabajo pendiente o en ejecución. Devuelve el trabajo actualizado,
    o None si no existe. Si ya terminó, lo devuelve sin cambios.

    - Pendiente: se reclama con el mismo .lock que usan los workers, así ninguno
      puede tomarlo a la vez, y queda cancelado en el momento.
    - En ejecución: se crea la marca .cancelar y el worker corta en el próximo
      lote. Si el worker no da señales hace rato (murió), se cancela sin esperarlo.
    """
    trabajo = obtener_trabajo(trabajo_id)
    if trabajo is None or trabajo["estado"] in ESTADOS_FINALES:
        return trabajo

    if trabajo["estado"] == "pendiente" and reclamar_trabajo(trabajo_id, "cancelado"):
        return actualizar_trabajo(trabajo_id, estado="cancelado", error="Cancelado antes de empezar.", fecha_fin=ahora_iso())

    # En ejecución (o un worker lo reclamó justo ahora)
    _archivo(trabajo_id, "cancelar").touch()
    latido = trabajo.get("latido")
    sin_senales = latido is None or (
        datetime.now(timezone.utc) - datetime.fromisoformat(latido)
    ).total_seconds() > LATIDO_MAXIMO_S
    if sin_senales:
        return _con_cancelacion(actualizar_trabajo(
            trabajo_id, estado="cancelado", fecha_fin=ahora_iso(),
            error="Cancelado sin respuesta del worker: no daba señales de vida, probablemente se detuvo.",
        ))
    return obtener_trabajo(trabajo_id)
