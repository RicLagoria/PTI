"""
Conversión de un aporte etiquetado con labelme a etiquetas YOLO.

Cada persona etiqueta con su propio labelme, así que los índices de clase que
le asignaría una herramienta como labelme2yolo dependen de en qué orden fue
apareciendo cada etiqueta en *sus* imágenes. Por eso acá no se confía en
ningún índice: se lee el nombre de cada etiqueta y se lo traduce a su posición
en la lista canónica (contratos/clases.json). Una etiqueta que no está en esa
lista hace rechazar el aporte entero, en vez de entrenar con datos corruptos.
"""
import base64
import io
import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
EXTENSION_POR_FORMATO = {"JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp", "TIFF": ".tif"}

# Tope de errores por archivo que se devuelven al usuario; el resto se resume.
MAX_ERRORES_INFORMADOS = 50


class ErrorAporte(Exception):
    """El aporte no se puede usar. `detalle` es lo que se le devuelve al usuario."""

    def __init__(self, mensaje: str, **extra):
        super().__init__(mensaje)
        self.detalle = {"mensaje": mensaje, **extra}


def normalizar_etiqueta(texto: str) -> str:
    """'  Maleza ' y 'maleza' son la misma clase: se ignoran mayúsculas y espacios de más."""
    return " ".join(str(texto).strip().lower().split())


def caja_de_forma(forma: Dict) -> Optional[Tuple[float, float, float, float]]:
    """Caja (x1, y1, x2, y2) que encierra una forma de labelme, o None si la forma no tiene área."""
    puntos = forma.get("points") or []
    # Las versiones viejas de labelme no guardan shape_type y todo es polígono
    tipo = forma.get("shape_type") or "polygon"
    if tipo == "circle" and len(puntos) == 2:
        (cx, cy), (px, py) = puntos
        radio = math.hypot(px - cx, py - cy)
        return cx - radio, cy - radio, cx + radio, cy + radio
    if tipo in ("rectangle", "polygon") and len(puntos) >= 2:
        xs = [float(p[0]) for p in puntos]
        ys = [float(p[1]) for p in puntos]
        return min(xs), min(ys), max(xs), max(ys)
    # "point", "line", "linestrip": no sirven para detección
    return None


def _buscar_imagen(ruta_json: Path, datos: Dict, raiz: Path) -> Optional[Path]:
    """
    Busca la imagen de una anotación sin salir de la carpeta del aporte:
    primero donde dice imagePath (labelme en Windows guarda barras invertidas)
    y si no, un archivo con el mismo nombre que el JSON.
    """
    raiz = raiz.resolve()
    candidatos = []
    ruta_declarada = str(datos.get("imagePath") or "").replace("\\", "/")
    if ruta_declarada:
        candidatos.append(ruta_json.parent / ruta_declarada)
        candidatos.append(ruta_json.parent / Path(ruta_declarada).name)
    candidatos += [ruta_json.with_suffix(ext) for ext in sorted(EXTENSIONES_IMAGEN)]
    candidatos += [ruta_json.with_suffix(ext.upper()) for ext in sorted(EXTENSIONES_IMAGEN)]

    for candidato in candidatos:
        try:
            resuelto = candidato.resolve()
        except OSError:
            continue
        # imagePath viene del usuario: que no pueda apuntar a archivos de otro lado del disco
        if raiz not in resuelto.parents:
            continue
        if resuelto.is_file() and resuelto.suffix.lower() in EXTENSIONES_IMAGEN:
            return resuelto
    return None


def _medir_imagen(origen) -> Tuple[int, int, str]:
    """Ancho, alto y extensión de una imagen (ruta o bytes). Falla si está dañada."""
    fuente = io.BytesIO(origen) if isinstance(origen, bytes) else origen
    with Image.open(fuente) as imagen:
        ancho, alto = imagen.size
        formato = imagen.format
        imagen.verify()
    return ancho, alto, EXTENSION_POR_FORMATO.get(formato, ".png")


def convertir_aporte(raiz: Path, clases: List[str]) -> Tuple[List[Dict], Dict]:
    """
    Recorre un aporte descomprimido y convierte cada JSON de labelme a líneas YOLO.

    Devuelve (anotaciones, resumen). Cada anotación trae la imagen de origen
    (`ruta` o, si venía embebida en el JSON, `bytes`), su `extension`, un
    `nombre` sugerido y las `lineas` YOLO. Lanza ErrorAporte si hay clases
    desconocidas o archivos que no se pueden usar: se rechaza todo el aporte.
    """
    indice_de_clase = {normalizar_etiqueta(c): i for i, c in enumerate(clases)}

    anotaciones: List[Dict] = []
    errores: List[str] = []
    desconocidas: Counter = Counter()
    cajas_por_clase: Counter = Counter()
    imagenes_usadas = set()
    formas_ignoradas = 0
    cajas_descartadas = 0

    for ruta_json in sorted(raiz.rglob("*.json")):
        relativo = ruta_json.relative_to(raiz).as_posix()
        try:
            datos = json.loads(ruta_json.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            errores.append(f"{relativo}: no es un JSON válido ({e})")
            continue
        # Otros JSON del ZIP (configuraciones, listados) no son anotaciones
        if not isinstance(datos, dict) or "shapes" not in datos:
            continue

        ruta_imagen = _buscar_imagen(ruta_json, datos, raiz)
        contenido = None
        if ruta_imagen is None:
            if not datos.get("imageData"):
                errores.append(f"{relativo}: no se encontró la imagen '{datos.get('imagePath')}' en el ZIP")
                continue
            try:
                contenido = base64.b64decode(datos["imageData"])
            except ValueError:
                errores.append(f"{relativo}: imageData no es base64 válido")
                continue

        try:
            ancho, alto, extension = _medir_imagen(contenido if contenido is not None else ruta_imagen)
        except Exception as e:
            errores.append(f"{relativo}: la imagen no se puede leer ({e})")
            continue
        if ruta_imagen is not None:
            extension = ruta_imagen.suffix.lower()
            imagenes_usadas.add(ruta_imagen)

        declarado = (datos.get("imageWidth"), datos.get("imageHeight"))
        if all(declarado) and tuple(declarado) != (ancho, alto):
            errores.append(
                f"{relativo}: se etiquetó sobre una imagen de {declarado[0]}x{declarado[1]} "
                f"pero la imagen mide {ancho}x{alto}"
            )
            continue

        lineas = []
        for forma in datos.get("shapes") or []:
            etiqueta = normalizar_etiqueta(forma.get("label", ""))
            if etiqueta not in indice_de_clase:
                desconocidas[forma.get("label", "")] += 1
                continue
            caja = caja_de_forma(forma)
            if caja is None:
                formas_ignoradas += 1
                continue
            x1, y1, x2, y2 = caja
            x1, x2 = max(0.0, x1), min(float(ancho), x2)
            y1, y2 = max(0.0, y1), min(float(alto), y2)
            if x2 - x1 < 1 or y2 - y1 < 1:
                cajas_descartadas += 1
                continue
            indice = indice_de_clase[etiqueta]
            lineas.append(
                f"{indice} {(x1 + x2) / 2 / ancho:.6f} {(y1 + y2) / 2 / alto:.6f} "
                f"{(x2 - x1) / ancho:.6f} {(y2 - y1) / alto:.6f}"
            )
            cajas_por_clase[clases[indice]] += 1

        anotaciones.append({
            "ruta": ruta_imagen,
            "bytes": contenido,
            "extension": extension,
            "nombre": ruta_json.stem,
            "lineas": lineas,
            "origen": relativo,
        })

    if desconocidas:
        raise ErrorAporte(
            "El aporte usa etiquetas que no están en la lista canónica de clases. "
            "Corregilas en labelme o pedí que se agreguen a contratos/clases.json.",
            clases_desconocidas=dict(desconocidas),
            clases_validas=clases,
        )
    if errores:
        raise ErrorAporte(
            f"{len(errores)} archivo(s) del aporte no se pueden usar.",
            errores=errores[:MAX_ERRORES_INFORMADOS],
            errores_omitidos=max(0, len(errores) - MAX_ERRORES_INFORMADOS),
        )
    if not anotaciones:
        raise ErrorAporte("El ZIP no tiene ninguna anotación de labelme (archivos .json con 'shapes').")

    todas = {p.resolve() for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES_IMAGEN}
    resumen = {
        "total_imagenes": len(anotaciones),
        "total_anotaciones": sum(cajas_por_clase.values()),
        "anotaciones_por_clase": {c: cajas_por_clase.get(c, 0) for c in clases},
        # Un JSON sin formas es una imagen de fondo explícita: entrena como ejemplo negativo
        "imagenes_sin_objetos": sum(1 for a in anotaciones if not a["lineas"]),
        # Una imagen sin JSON puede ser un descuido, no un fondo: se ignora y se informa
        "imagenes_sin_anotar": len(todas - imagenes_usadas),
        "formas_ignoradas": formas_ignoradas,
        "cajas_descartadas": cajas_descartadas,
    }
    return anotaciones, resumen
