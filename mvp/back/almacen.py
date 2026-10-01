import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import rasterio
import rasterio.shutil
from rasterio.errors import RasterioIOError
from rio_tiler.io import Reader

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "data/imagenes"))
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "8192")) * 1024 * 1024

EXTENSIONES_VALIDAS = (".tif", ".tiff")
NOMBRE_SUBIDA = "subida.tif"
NOMBRE_COG = "imagen.tif"
NOMBRE_META = "meta.json"
NOMBRE_DETECCIONES = "detecciones.json"

_PATRON_ID = re.compile(r"^[0-9a-f]{32}$")


class ImagenInvalida(Exception):
    """El archivo subido no sirve como ortomosaico (no es GeoTIFF o no tiene georreferencia)."""


def crear_carpeta_nueva():
    """Reserva una carpeta para una subida y retorna (imagen_id, ruta_archivo_crudo)."""
    imagen_id = uuid.uuid4().hex
    carpeta = UPLOAD_DIR / imagen_id
    carpeta.mkdir(parents=True)
    return imagen_id, carpeta / NOMBRE_SUBIDA


def carpeta_de(imagen_id):
    """
    Retorna la carpeta de una imagen ya procesada o None si no existe.
    El id solo puede ser un UUID hex, así nunca se arma una ruta fuera de UPLOAD_DIR.
    """
    if not _PATRON_ID.match(imagen_id):
        return None
    carpeta = UPLOAD_DIR / imagen_id
    if not (carpeta / NOMBRE_META).is_file():
        return None
    return carpeta


def descartar(imagen_id):
    shutil.rmtree(UPLOAD_DIR / imagen_id, ignore_errors=True)


def finalizar_subida(imagen_id, nombre_original):
    """
    Valida el archivo crudo, lo deja como COG y escribe meta.json.
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
            "maxzoom": cog.maxzoom
        }

    with open(carpeta / NOMBRE_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def leer_meta(carpeta):
    with open(carpeta / NOMBRE_META, encoding="utf-8") as f:
        return json.load(f)


def listar():
    """Imágenes ya procesadas, de la más reciente a la más antigua."""
    if not UPLOAD_DIR.is_dir():
        return []
    metas = [leer_meta(p.parent) for p in UPLOAD_DIR.glob(f"*/{NOMBRE_META}")]
    return sorted(metas, key=lambda m: m["fecha_subida"], reverse=True)
