import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import rasterio
import rasterio.shutil
from rasterio.errors import RasterioIOError
from rio_tiler.io import Reader


def _obtener_upload_dir() -> Path:
    env_dir = os.environ.get("UPLOAD_DIR")
    if env_dir:
        return Path(env_dir)

    candidatos = [
        Path("datos/ortomosaicos"),
        Path("../datos/ortomosaicos"),
        Path("../../datos/ortomosaicos"),
        Path("/data/imagenes"),
        Path("../data/imagenes"),
        Path("data/imagenes"),
    ]
    for c in candidatos:
        if c.is_dir():
            return c

    # Por defecto
    ruta_defecto = Path("datos/ortomosaicos")
    ruta_defecto.mkdir(parents=True, exist_ok=True)
    return ruta_defecto


UPLOAD_DIR = _obtener_upload_dir()
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "8192")) * 1024 * 1024

EXTENSIONES_VALIDAS = (".tif", ".tiff")
NOMBRE_SUBIDA = "subida.tif"
NOMBRE_COG = "imagen.tif"
# meta.json y detecciones.json ya no se escriben: esa metadata y las
# detecciones viven en Postgres (ver datos.py). Acá solo queda el .tif.

_PATRON_ID = re.compile(r"^[0-9a-f]{32}$")


def validar_id(imagen_id: str) -> bool:
    """El id solo puede ser un UUID hex: así nunca se arma una ruta fuera de UPLOAD_DIR."""
    return bool(_PATRON_ID.match(imagen_id))


class ImagenInvalida(Exception):
    """El archivo subido no sirve como ortomosaico (no es GeoTIFF o no tiene georreferencia)."""


def crear_carpeta_nueva() -> Tuple[str, Path]:
    """Reserva una carpeta para una subida y retorna (imagen_id, ruta_archivo_crudo)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    imagen_id = uuid.uuid4().hex
    carpeta = UPLOAD_DIR / imagen_id
    carpeta.mkdir(parents=True, exist_ok=True)
    return imagen_id, carpeta / NOMBRE_SUBIDA


def descartar(imagen_id: str):
    shutil.rmtree(UPLOAD_DIR / imagen_id, ignore_errors=True)


def finalizar_subida(imagen_id: str, nombre_original: str) -> Dict:
    """
    Valida el archivo crudo y lo deja como COG. Devuelve la metadata para que
    el caller la persista en la tabla ortomosaicos (ver datos.py).
    Lanza ImagenInvalida si no es un GeoTIFF georreferenciado.
    """
    carpeta = UPLOAD_DIR / imagen_id
    ruta_cruda = carpeta / NOMBRE_SUBIDA
    ruta_cog = carpeta / NOMBRE_COG

    try:
        with rasterio.open(ruta_cruda) as src:
            if src.driver != "GTiff":
                raise ImagenInvalida("El archivo no es un TIFF.")
            if src.crs is None:
                raise ImagenInvalida("El TIFF no tiene georreferencia (sin sistema de coordenadas).")
            ya_es_cog = src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
    except RasterioIOError:
        raise ImagenInvalida("El archivo no es un TIFF legible.")

    if ya_es_cog:
        if ruta_cog.exists():
            ruta_cog.unlink()
        ruta_cruda.rename(ruta_cog)
    else:
        # El servidor de teselas necesita overviews y bloques internos para leer por zoom
        rasterio.shutil.copy(ruta_cruda, ruta_cog, driver="COG", COMPRESS="DEFLATE", BIGTIFF="IF_SAFER")
        ruta_cruda.unlink()

    with Reader(str(ruta_cog)) as cog:
        oeste, sur, este, norte = cog.get_geographic_bounds(rasterio.crs.CRS.from_epsg(4326))
        meta = {
            "id": imagen_id,
            "nombre": nombre_original,
            "fecha_subida": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ancho_px": cog.dataset.width,
            "alto_px": cog.dataset.height,
            "bounds": [
                [sur, oeste],   # Suroeste [lat, lon]
                [norte, este]   # Noreste [lat, lon]
            ],
            "minzoom": cog.minzoom,
            "maxzoom": cog.maxzoom,
            "ruta_archivo": str(ruta_cog),
        }

    return meta

