import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional


def _obtener_dir_modelos() -> Path:
    env_dir = os.environ.get("MODELOS_DIR")
    if env_dir:
        return Path(env_dir)

    candidatos = [
        Path("datos/modelos"),
        Path("../datos/modelos"),
        Path("../../datos/modelos"),
        Path("../../../datos/modelos"),
        Path("/data/modelos"),
        Path("data/modelos"),
    ]
    for c in candidatos:
        if c.is_dir():
            return c

    ruta = Path("datos/modelos")
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


MODELOS_DIR = _obtener_dir_modelos()


def listar_modelos() -> List[Dict]:
    """Lista las versiones registradas de modelos."""
    if not MODELOS_DIR.is_dir():
        return []

    modelos = []
    for d in sorted(MODELOS_DIR.iterdir()):
        if d.is_dir() and d.name != "activo":
            meta_file = d / "meta.json"
            best_pt = d / "best.pt"
            if best_pt.is_file():
                meta = {}
                if meta_file.is_file():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                modelos.append({
                    "version": d.name,
                    "activo": (MODELOS_DIR / "activo" / "version.txt").read_text().strip() == d.name if (MODELOS_DIR / "activo" / "version.txt").is_file() else False,
                    "tamano_mb": round(best_pt.stat().st_size / (1024 * 1024), 2),
                    "meta": meta
                })

    return modelos


def ruta_pesos_activos() -> Optional[Path]:
    activo_pt = MODELOS_DIR / "activo" / "best.pt"
    if activo_pt.is_file():
        return activo_pt

    # Fallback al primer modelo disponible o train-3 si existe
    candidatos = list(MODELOS_DIR.glob("*/best.pt"))
    if candidatos:
        return candidatos[0]
    return None


def activar_modelo(version: str) -> bool:
    """Activa una versión copiando sus pesos a datos/modelos/activo/best.pt de forma atómica."""
    carpeta_version = MODELOS_DIR / version
    pesos_origen = carpeta_version / "best.pt"
    if not pesos_origen.is_file():
        return False

    carpeta_activo = MODELOS_DIR / "activo"
    carpeta_activo.mkdir(parents=True, exist_ok=True)

    destino_pt = carpeta_activo / "best.pt"
    destino_temp = carpeta_activo / "best.pt.tmp"

    shutil.copy2(pesos_origen, destino_temp)
    if destino_pt.exists():
        destino_pt.unlink()
    destino_temp.rename(destino_pt)

    (carpeta_activo / "version.txt").write_text(version, encoding="utf-8")
    return True

