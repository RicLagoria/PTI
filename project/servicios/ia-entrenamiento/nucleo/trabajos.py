import json
import os
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


def encolar_trabajo(datasets: List[str], epocas: int = 50, imgsz: int = 640, pesos_base: str = "yolov8n.pt") -> Dict:
    TRABAJOS_DIR.mkdir(parents=True, exist_ok=True)
    trabajo_id = uuid.uuid4().hex[:12]
    archivo_trabajo = TRABAJOS_DIR / f"{trabajo_id}.json"

    trabajo = {
        "id": trabajo_id,
        "estado": "pendiente",  # pendiente, ejecutando, completado, fallido
        "fecha_creacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "datasets": datasets,
        "epocas": epocas,
        "imgsz": imgsz,
        "pesos_base": pesos_base,
        "progreso_epocas": 0,
        "metricas": {},
        "version_generada": None,
        "error": None
    }

    with open(archivo_trabajo, "w", encoding="utf-8") as f:
        json.dump(trabajo, f, indent=2)

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

    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return data


def obtener_siguiente_pendiente() -> Optional[Dict]:
    pendientes = [t for t in listar_trabajos() if t["estado"] == "pendiente"]
    if pendientes:
        # El más antiguo primero
        return sorted(pendientes, key=lambda x: x["fecha_creacion"])[0]
    return None

