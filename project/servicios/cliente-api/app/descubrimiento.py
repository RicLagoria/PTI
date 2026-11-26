"""
Descubrimiento de servicios del lado del consumidor (Entrega 4 de PDC).

`instancias("ia-inferencia", url_fija)` devuelve las URL vivas según
registro-servicios, rotadas para repartir la carga entre réplicas. La respuesta
se guarda en caché CACHE_S segundos para no consultar el registro en cada lote.

Degradación ordenada: sin REGISTRO_URL, con el registro caído o sin instancias
anunciadas, devuelve `[url_fija]` (IA_INFERENCIA_URL). Así el registro nunca es
un punto único de falla: en el peor caso el sistema vuelve a la configuración
estática que tenía antes de esta entrega.
"""
import itertools
import os
import threading
import time
from typing import Dict, List, Tuple

import httpx

REGISTRO_URL = os.environ.get("REGISTRO_URL", "").rstrip("/")
CACHE_S = float(os.environ.get("REGISTRO_CACHE_S", "2"))

_cache: Dict[str, Tuple[float, List[str]]] = {}
_turnos: Dict[str, "itertools.count[int]"] = {}
_candado = threading.Lock()


def _consultar_registro(nombre: str) -> List[str]:
    try:
        res = httpx.get(f"{REGISTRO_URL}/servicios/{nombre}", timeout=2)
        res.raise_for_status()
        return [i["url"] for i in res.json()["instancias"]]
    except Exception as e:
        print(f"[DESCUBRIMIENTO] Registro no disponible ({e}); uso la URL fija.")
        return []


def instancias(nombre: str, url_fija: str) -> List[str]:
    """URL candidatas para `nombre`, empezando por la que le toca en la rotación."""
    if not REGISTRO_URL:
        return [url_fija]
    ahora = time.monotonic()
    with _candado:
        guardado = _cache.get(nombre)
    if guardado and ahora - guardado[0] < CACHE_S:
        urls = guardado[1]
    else:
        urls = _consultar_registro(nombre)
        with _candado:
            _cache[nombre] = (ahora, urls)
    if not urls:
        return [url_fija]
    with _candado:
        turno = next(_turnos.setdefault(nombre, itertools.count()))
    desde = turno % len(urls)
    return urls[desde:] + urls[:desde]


def invalidar(nombre: str):
    """Olvida la caché: la próxima consulta vuelve a preguntar al registro."""
    with _candado:
        _cache.pop(nombre, None)
