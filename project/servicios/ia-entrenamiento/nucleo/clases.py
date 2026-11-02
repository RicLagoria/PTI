import json
from pathlib import Path
from typing import List

CLASES_DEFECTO = ["maleza", "falla"]


def _ruta_clases_json() -> Path:
    candidatos = [
        Path("contratos/clases.json"),
        Path("../contratos/clases.json"),
        Path("../../contratos/clases.json"),
        Path("../../../contratos/clases.json"),
        Path("/contratos/clases.json"),
    ]
    for c in candidatos:
        if c.is_file():
            return c
    return Path("contratos/clases.json")


def obtener_clases_canonicas() -> List[str]:
    """Retorna la lista ordenada de clases canónicas. El índice coincide con las etiquetas YOLO."""
    ruta = _ruta_clases_json()
    if ruta.is_file():
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return CLASES_DEFECTO

