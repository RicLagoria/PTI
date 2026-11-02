"""
Exclusión mutua para los análisis de una imagen (Entrega 3 de PDC, caso P1).

Problema: dos análisis simultáneos sobre el mismo ortomosaico escribían el mismo
`detecciones.json`; gana el que termina último y el resultado del otro se pierde
o queda mezclado, además de duplicar el consumo de CPU.

Solución, en dos piezas:

1. `BloqueoImagen`: un lock exclusivo por imagen (`flock` sobre `analisis.lock`
   dentro de la carpeta de la imagen). Si ya hay un análisis activo, el segundo
   no espera ni pisa nada: recibe `AnalisisEnCurso` (el servidor responde 409).
   `flock` vive en el kernel, así que funciona entre hilos y entre procesos de
   uvicorn, y si el proceso muere el sistema operativo lo libera solo.
2. `escribir_json_atomico`: se escribe a un temporal y se renombra con
   `os.replace`. Un lector nunca ve un JSON a medias.

Solo Linux/macOS (usa `fcntl`); los contenedores del proyecto son Linux.
"""
import fcntl
import json
import os
import tempfile
from pathlib import Path

NOMBRE_LOCK = "analisis.lock"


class AnalisisEnCurso(Exception):
    """Ya hay un análisis corriendo sobre esa imagen."""


class BloqueoImagen:
    """Lock exclusivo y no bloqueante sobre la carpeta de una imagen."""

    def __init__(self, carpeta: Path):
        self._ruta = Path(carpeta) / NOMBRE_LOCK
        self._archivo = None

    def adquirir(self):
        # Cada open() crea una "open file description" nueva, y flock excluye
        # entre descriptores distintos aunque sean del mismo proceso: por eso
        # sirve también para dos hilos de la misma API.
        archivo = open(self._ruta, "a+")
        try:
            fcntl.flock(archivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            archivo.close()
            raise AnalisisEnCurso()
        self._archivo = archivo

    def liberar(self):
        if self._archivo is not None:
            try:
                fcntl.flock(self._archivo, fcntl.LOCK_UN)
            finally:
                self._archivo.close()
                self._archivo = None


def hay_analisis_activo(carpeta: Path) -> bool:
    """True si alguien tiene el lock de esa imagen (sin quedarse con él)."""
    prueba = BloqueoImagen(carpeta)
    try:
        prueba.adquirir()
    except AnalisisEnCurso:
        return True
    prueba.liberar()
    return False


def escribir_json_atomico(ruta, datos):
    """Escribe `datos` como JSON sin que nadie pueda leer el archivo a medias."""
    ruta = Path(ruta)
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=ruta.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        try:
            os.unlink(temporal)
        except FileNotFoundError:
            pass
        raise
