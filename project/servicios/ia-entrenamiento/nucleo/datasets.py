import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from clases import obtener_clases_canonicas


def _obtener_dir_datasets() -> Path:
    env_dir = os.environ.get("DATASETS_DIR")
    if env_dir:
        return Path(env_dir)

    candidatos = [
        Path("datos/datasets"),
        Path("../datos/datasets"),
        Path("../../datos/datasets"),
        Path("/data/datasets"),
        Path("data/datasets"),
    ]
    for c in candidatos:
        if c.is_dir():
            return c

    ruta = Path("datos/datasets")
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


DATASETS_DIR = _obtener_dir_datasets()


def listar_datasets() -> List[Dict]:
    if not DATASETS_DIR.is_dir():
        return []

    res = []
    for d in sorted(DATASETS_DIR.iterdir()):
        if d.is_dir():
            meta_path = d / "meta.json"
            if meta_path.is_file():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        res.append(json.load(f))
                except Exception:
                    pass
    return res


def eliminar_dataset(dataset_id: str) -> bool:
    carpeta = DATASETS_DIR / dataset_id
    if carpeta.is_dir():
        shutil.rmtree(carpeta, ignore_errors=True)
        return True
    return False


def guardar_dataset_zip(archivo_bytes: bytes, nombre_original: str) -> Dict:
    """Extrae un archivo ZIP de dataset, valida imágenes y JSONs y genera meta.json."""
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    dataset_id = uuid.uuid4().hex[:12]
    carpeta = DATASETS_DIR / dataset_id
    carpeta.mkdir(parents=True, exist_ok=True)

    zip_path = carpeta / "dataset.zip"
    zip_path.write_bytes(archivo_bytes)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(carpeta / "extraido")

    zip_path.unlink()

    # Contar imágenes
    extensiones_img = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    imagenes = [p for p in (carpeta / "extraido").rglob("*") if p.suffix.lower() in extensiones_img]

    meta = {
        "id": dataset_id,
        "nombre": nombre_original,
        "fecha_subida": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_imagenes": len(imagenes),
        "clases_canonicas": obtener_clases_canonicas()
    }

    with open(carpeta / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta

