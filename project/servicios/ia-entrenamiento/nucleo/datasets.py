import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional

from clases import obtener_clases_canonicas
from conversion_labelme import ErrorAporte, convertir_aporte

# El id lo genera el servidor (uuid4 hex recortado) y viaja en las URLs. Validarlo
# antes de armar una ruta impide cosas como DELETE /datasets/%2e%2e, que haría
# rmtree sobre la carpeta padre de los datasets.
ID_VALIDO = re.compile(r"^[0-9a-f]{12}$")

# Tope del contenido descomprimido, contra ZIPs que se inflan hasta llenar el disco
MAX_DESCOMPRIMIDO_MB = int(os.environ.get("MAX_DESCOMPRIMIDO_MB", "8192"))


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


def carpeta_de(dataset_id: str) -> Optional[Path]:
    """Carpeta de un dataset ya guardado, o None si el id no es válido o no existe."""
    if not ID_VALIDO.match(dataset_id or ""):
        return None
    carpeta = DATASETS_DIR / dataset_id
    return carpeta if (carpeta / "meta.json").is_file() else None


def leer_meta(dataset_id: str) -> Optional[Dict]:
    carpeta = carpeta_de(dataset_id)
    if carpeta is None:
        return None
    with open(carpeta / "meta.json", "r", encoding="utf-8") as f:
        return json.load(f)


def listar_datasets() -> List[Dict]:
    if not DATASETS_DIR.is_dir():
        return []

    res = []
    for d in sorted(DATASETS_DIR.iterdir()):
        # Las carpetas que empiezan con "." son subidas a medio procesar
        if d.is_dir() and not d.name.startswith("."):
            meta_path = d / "meta.json"
            if meta_path.is_file():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        res.append(json.load(f))
                except Exception:
                    pass
    return res


def eliminar_dataset(dataset_id: str) -> bool:
    carpeta = carpeta_de(dataset_id)
    if carpeta is None:
        return False
    shutil.rmtree(carpeta, ignore_errors=True)
    return True


def _nombre_unico(base: str, usados: set) -> str:
    """Dos imágenes de subcarpetas distintas pueden llamarse igual: se numeran."""
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "imagen"
    nombre, n = limpio, 1
    while nombre.lower() in usados:
        n += 1
        nombre = f"{limpio}_{n}"
    usados.add(nombre.lower())
    return nombre


def guardar_dataset_zip(archivo_zip: BinaryIO, nombre: str, archivo_original: str) -> Dict:
    """
    Valida un ZIP de labelme, lo convierte a YOLO con los índices canónicos y
    lo guarda como DATASETS_DIR/<id>/{imagenes,etiquetas}/ + meta.json.

    Se arma todo en una carpeta temporal y recién al final se renombra, así un
    aporte rechazado o una subida cortada nunca queda a medias en el listado.
    Lanza ErrorAporte con el detalle para el usuario si el aporte no sirve.
    """
    clases = obtener_clases_canonicas()
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    dataset_id = uuid.uuid4().hex[:12]
    temporal = DATASETS_DIR / f".subiendo-{dataset_id}"

    try:
        extraido = temporal / "extraido"
        try:
            with zipfile.ZipFile(archivo_zip) as zf:
                descomprimido = sum(i.file_size for i in zf.infolist())
                if descomprimido > MAX_DESCOMPRIMIDO_MB * 1024 * 1024:
                    raise ErrorAporte(
                        f"El ZIP descomprimido ocupa {descomprimido // (1024 * 1024)} MB; "
                        f"el máximo es {MAX_DESCOMPRIMIDO_MB} MB."
                    )
                # extractall ya descarta rutas absolutas y componentes ".."
                zf.extractall(extraido)
        except zipfile.BadZipFile:
            raise ErrorAporte("El archivo no es un ZIP válido.")

        anotaciones, resumen = convertir_aporte(extraido, clases)

        carpeta_imagenes = temporal / "imagenes"
        carpeta_etiquetas = temporal / "etiquetas"
        carpeta_imagenes.mkdir(parents=True)
        carpeta_etiquetas.mkdir(parents=True)

        usados: set = set()
        for anotacion in anotaciones:
            nombre_archivo = _nombre_unico(anotacion["nombre"], usados)
            destino = carpeta_imagenes / f"{nombre_archivo}{anotacion['extension']}"
            if anotacion["bytes"] is not None:
                destino.write_bytes(anotacion["bytes"])
            else:
                shutil.copy2(anotacion["ruta"], destino)
            texto = "\n".join(anotacion["lineas"])
            (carpeta_etiquetas / f"{nombre_archivo}.txt").write_text(
                texto + "\n" if texto else "", encoding="utf-8"
            )

        shutil.rmtree(extraido)

        meta = {
            "id": dataset_id,
            "nombre": nombre,
            "archivo_original": archivo_original,
            "fecha_creacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            # Lista canónica vigente al convertir: los índices de las etiquetas
            # apuntan a esta lista, y el entrenamiento verifica que siga siendo
            # un prefijo de la actual (las clases nuevas solo se agregan al final).
            "clases": clases,
            **resumen,
        }
        with open(temporal / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        temporal.rename(DATASETS_DIR / dataset_id)
        return meta
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise
