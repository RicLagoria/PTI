"""
Conversión de un aporte etiquetado con labelme a etiquetas YOLO.

Cada persona etiqueta con su propio labelme, así que los índices de clase que
le asignaría una herramienta como labelme2yolo dependen de en qué orden fue
apareciendo cada etiqueta en *sus* imágenes. Por eso acá no se confía en
ningún índice: se lee el nombre de cada etiqueta y se lo traduce a su posición
en la lista canónica (contratos/clases.json). Una etiqueta que no está en esa
lista hace rechazar el aporte entero, en vez de entrenar con datos corruptos.

De cada forma se sacan las dos etiquetas que YOLO puede consumir, porque un
mismo aporte sirve para entrenar detección o segmentación:

- caja (`clase cx cy w h`), que es lo que entrena un modelo `detect`;
- contorno (`clase x1 y1 x2 y2 … xn yn`), que entrena un modelo `segment`.

El contorno es el dato que el equipo ya venía dibujando en labelme y que la
versión anterior tiraba al reducir cada forma a su caja. Las formas que no
tienen contorno propio (un `rectangle`) igual generan uno con las cuatro
esquinas de la caja, y se cuentan aparte en el resumen: entrenar segmentación
con esos contornos solo le enseña rectángulos al modelo.
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

# Vértices con los que se aproxima un "circle" de labelme: ni YOLO ni GeoJSON
# tienen círculos, así que el contorno tiene que ser un polígono.
VERTICES_CIRCULO = 16

# Un contorno necesita al menos un triángulo para encerrar área
MIN_VERTICES = 3


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


def contorno_de_forma(forma: Dict) -> Optional[Tuple[List[Tuple[float, float]], bool]]:
    """
    Contorno de una forma de labelme como lista de vértices, y si es un contorno
    propio o uno derivado de la caja. None si la forma no encierra área.

    - "polygon": los vértices tal como se dibujaron (el caso normal del equipo).
    - "circle": se aproxima con VERTICES_CIRCULO vértices.
    - "rectangle": las cuatro esquinas. Es un contorno "de caja": sirve para que
      el aporte no quede sin etiquetas de segmentación, pero no aporta forma.
    """
    puntos = forma.get("points") or []
    tipo = forma.get("shape_type") or "polygon"

    if tipo == "circle" and len(puntos) == 2:
        (cx, cy), (px, py) = puntos
        radio = math.hypot(float(px) - float(cx), float(py) - float(cy))
        if radio <= 0:
            return None
        paso = 2 * math.pi / VERTICES_CIRCULO
        return [
            (float(cx) + radio * math.cos(i * paso), float(cy) + radio * math.sin(i * paso))
            for i in range(VERTICES_CIRCULO)
        ], True

    if tipo == "polygon" and len(puntos) >= MIN_VERTICES:
        return [(float(p[0]), float(p[1])) for p in puntos], True

    if tipo == "rectangle" and len(puntos) >= 2:
        caja = caja_de_forma(forma)
        if caja is None:
            return None
        x1, y1, x2, y2 = caja
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], False

    # Un "polygon" de 2 puntos es una línea: tiene caja pero no encierra nada
    return None


def _normalizar_contorno(
    vertices: List[Tuple[float, float]], ancho: int, alto: int
) -> Optional[List[Tuple[float, float]]]:
    """
    Lleva el contorno a las coordenadas relativas que espera YOLO (0 a 1), recortado
    al rectángulo de la imagen. Devuelve None si quedan menos de MIN_VERTICES
    vértices distintos, es decir si ya no encierra nada.

    El recorte es vértice por vértice (se pega al borde), no un recorte
    geométrico del polígono: alcanza para etiquetas que apenas se pasan del
    borde, que es lo que pasa cuando se etiqueta sobre una tesela.
    """
    relativos = []
    for x, y in vertices:
        rx = min(1.0, max(0.0, x / ancho))
        ry = min(1.0, max(0.0, y / alto))
        # Los vértices repetidos (consecutivos o por el recorte) no aportan
        if not relativos or (round(rx, 6), round(ry, 6)) != relativos[-1]:
            relativos.append((round(rx, 6), round(ry, 6)))
    if len(relativos) > 1 and relativos[0] == relativos[-1]:
        relativos.pop()
    return relativos if len(set(relativos)) >= MIN_VERTICES else None


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


def convertir_aporte(
    raiz: Path, clases: List[str], fondos_implicitos: bool = False
) -> Tuple[List[Dict], Dict]:
    """
    Recorre un aporte descomprimido y convierte cada JSON de labelme a líneas YOLO.

    Devuelve (anotaciones, resumen). Cada anotación trae la imagen de origen
    (`ruta` o, si venía embebida en el JSON, `bytes`), su `extension`, un
    `nombre` sugerido, las `lineas` de cajas y las `lineas_contorno` de
    segmentación. Lanza ErrorAporte si hay clases desconocidas o archivos que no
    se pueden usar: se rechaza todo el aporte.

    Con `fondos_implicitos`, las imágenes que no tienen .json entran como
    ejemplo negativo en vez de ignorarse. No es lo mismo que ignorarlas: una
    imagen ignorada no le enseña nada al modelo y una declarada como fondo le
    enseña que ahí no hay maleza, así que si el lote está a medio etiquetar esto
    lo arruina. Por eso viene apagado y lo pide quien sube el aporte.
    """
    indice_de_clase = {normalizar_etiqueta(c): i for i, c in enumerate(clases)}

    anotaciones: List[Dict] = []
    errores: List[str] = []
    desconocidas: Counter = Counter()
    cajas_por_clase: Counter = Counter()
    contornos_por_clase: Counter = Counter()
    imagenes_usadas = set()
    formas_ignoradas = 0
    cajas_descartadas = 0
    contornos_descartados = 0
    contornos_de_caja = 0

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
        lineas_contorno = []
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

            # La caja ya se guardó: una forma sin contorno usable (una línea con
            # caja, un polígono que el recorte deja sin área) solo pierde la
            # etiqueta de segmentación, el aporte sigue sirviendo para detección.
            contorno = contorno_de_forma(forma)
            relativos = _normalizar_contorno(contorno[0], ancho, alto) if contorno else None
            if relativos is None:
                contornos_descartados += 1
                continue
            if not contorno[1]:
                contornos_de_caja += 1
            lineas_contorno.append(
                f"{indice} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in relativos)
            )
            contornos_por_clase[clases[indice]] += 1

        anotaciones.append({
            "ruta": ruta_imagen,
            "bytes": contenido,
            "extension": extension,
            "nombre": ruta_json.stem,
            "lineas": lineas,
            "lineas_contorno": lineas_contorno,
            "origen": relativo,
        })

    if desconocidas:
        raise ErrorAporte(
            "El aporte usa etiquetas que no están en la lista canónica de clases. "
            "Corregilas en labelme o pedí que se agreguen a contratos/clases.json.",
            clases_desconocidas=dict(desconocidas),
            clases_validas=clases,
        )
    todas = {p.resolve() for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES_IMAGEN}
    sin_anotar = sorted(todas - imagenes_usadas)
    fondos_declarados = 0

    if fondos_implicitos:
        for ruta_imagen in sin_anotar:
            relativo = ruta_imagen.relative_to(raiz).as_posix()
            try:
                # Se mide igual que una imagen con .json: una imagen rota tiene
                # que rechazar el aporte acá y no reventar al entrenar
                _medir_imagen(ruta_imagen)
            except Exception as e:
                errores.append(f"{relativo}: la imagen no se puede leer ({e})")
                continue
            anotaciones.append({
                "ruta": ruta_imagen,
                "bytes": None,
                "extension": ruta_imagen.suffix.lower(),
                "nombre": ruta_imagen.stem,
                # Sin formas: es exactamente lo que escribe un .json vacío
                "lineas": [],
                "lineas_contorno": [],
                "origen": relativo,
            })
            fondos_declarados += 1

    if errores:
        raise ErrorAporte(
            f"{len(errores)} archivo(s) del aporte no se pueden usar.",
            errores=errores[:MAX_ERRORES_INFORMADOS],
            errores_omitidos=max(0, len(errores) - MAX_ERRORES_INFORMADOS),
        )
    if not anotaciones:
        raise ErrorAporte("El ZIP no tiene ninguna anotación de labelme (archivos .json con 'shapes').")

    total_contornos = sum(contornos_por_clase.values())
    resumen = {
        "total_imagenes": len(anotaciones),
        "total_anotaciones": sum(cajas_por_clase.values()),
        "anotaciones_por_clase": {c: cajas_por_clase.get(c, 0) for c in clases},
        # Un JSON sin formas es una imagen de fondo explícita: entrena como ejemplo negativo
        "imagenes_sin_objetos": sum(1 for a in anotaciones if not a["lineas"]),
        # Una imagen sin JSON puede ser un descuido, no un fondo: se ignora y se
        # informa. Con fondos_implicitos no queda ninguna, porque entraron todas
        # como ejemplo negativo; cuántas fueron se dice aparte.
        "imagenes_sin_anotar": 0 if fondos_implicitos else len(sin_anotar),
        # Imágenes sin .json que se declararon fondo al subir, en vez de ignorarse
        "fondos_declarados": fondos_declarados,
        "formas_ignoradas": formas_ignoradas,
        "cajas_descartadas": cajas_descartadas,
        # Segmentación: con qué se puede entrenar un modelo "segment". Un aporte
        # etiquetado con rectángulos tiene contornos, pero todos son de caja.
        "total_contornos": total_contornos,
        "contornos_por_clase": {c: contornos_por_clase.get(c, 0) for c in clases},
        "contornos_de_caja": contornos_de_caja,
        "contornos_descartados": contornos_descartados,
        # Si el aporte sirve para entrenar segmentación. No alcanza con "tiene
        # contornos": un aporte de puros fondos (un .json sin formas por imagen,
        # o `fondos_implicitos` al subirlo) no tiene ninguno y sin
        # embargo sirve igual para las dos tareas, porque lo que aporta es
        # justamente que no hay nada que encontrar. Lo que no sirve es un aporte
        # con cajas pero sin contornos: entrenar segmentación con eso le
        # enseñaría al modelo que esas malezas son fondo.
        "tiene_segmentacion": total_contornos > 0 or sum(cajas_por_clase.values()) == 0,
    }
    return anotaciones, resumen
