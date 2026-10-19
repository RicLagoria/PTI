import json
import os
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


def encolar_trabajo(datasets: List[str], epocas: int = 50, imgsz: int = 640, pesos_base: str = "yolov8n.pt") -> Dict:
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
                res.append(json.load(arch))
        except Exception:
            pass
    return res


def obtener_trabajo(trabajo_id: str) -> Optional[Dict]:
    archivo = TRABAJOS_DIR / f"{trabajo_id}.json"
    if archivo.is_file():
        try:
            with open(archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def actualizar_trabajo(trabajo_id: str, **kwargs) -> Optional[Dict]:
    archivo = TRABAJOS_DIR / f"{trabajo_id}.json"
    if not archivo.is_file():
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
    lock = TRABAJOS_DIR / f"{trabajo_id}.lock"
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
            return actualizar_trabajo(trabajo["id"], estado="ejecutando", worker=worker)
    return None
