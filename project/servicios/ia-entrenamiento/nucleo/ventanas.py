"""
Aportes de escala gruesa derivados de un aporte ya subido.

El modelo mira el campo a través de una tesela de 640 px, que en un ortomosaico
de 3,3 cm/px son unos 21 m. Una mancha más grande no entra en la imagen y el
modelo nunca la ve entera, así que aprende a cortarla: en el dataset de El Azul
una de cada cuatro manchas etiquetadas toca el borde de su tesela, y el
percentil 95 del lado está pegado al tamaño de la tesela. La distribución está
cortada por el encuadre, no por el campo.

Acá se arma la escala gruesa sin que haya que etiquetar nada de nuevo: se pegan
N×N teselas vecinas, el resultado se reduce al lado de entrada del modelo y las
etiquetas se recomponen con el desplazamiento de cada tesela y el factor de
reducción. Una ventana de 4×4 cubre unos 89 m, así que la mancha que estaba
cortada aparece entera.

Lo que lo hace posible es que las teselas conserven su posición en el nombre
(`tile_x<col>_y<fila>`): `datasets.guardar_dataset_zip` guarda cada imagen con el
nombre del .json de origen, así que la vecindad sobrevive a la subida y este
módulo puede trabajar sobre el aporte ya guardado, sin pedir el ZIP de nuevo.

Cada escala se registra como un aporte más, con su propio id, que se mezcla en un
entrenamiento igual que cualquier otro.
"""
import json
import re
import shutil
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

import datasets
from conversion_labelme import ErrorAporte

# La posición de la tesela dentro del ortomosaico, que es lo único que dice
# cuáles son vecinas. Las teselas que no la lleven en el nombre quedan afuera.
PATRON_TESELA = re.compile(r"tile_x(\d+)_y(\d+)", re.IGNORECASE)

# Lado de la imagen generada. Pegar N×N teselas y reducir a este tamaño es lo que
# "aleja la cámara": el mismo encuadre con N veces más campo. Es el imgsz por
# defecto de un entrenamiento; una corrida con otro imgsz reescala igual.
LADO_SALIDA = 640

# La misma calidad con la que cliente-api codifica las teselas que le manda a
# ia-inferencia, para entrenar sobre el mismo nivel de compresión del análisis.
CALIDAD_JPEG = 90

# Un vértice a menos de esto de una costura interna cuenta como pegado a ella y
# su forma entra en la unión. Las etiquetas se dibujaron tesela por tesela, así
# que las dos mitades de una mancha no coinciden al píxel sobre la costura.
MARGEN_COSTURA = 4
# Cierra huecos de unos pocos píxeles entre las dos mitades antes de volver a
# trazar el contorno; sin esto quedarían dos contornos pegados en vez de uno.
CIERRE_PX = 5

# Igual que en ia-inferencia: el contorno de una máscara trae cientos de
# vértices casi colineales, y la tolerancia va relativa al perímetro para que
# una mancha chica no termine convertida en un triángulo.
TOLERANCIA_SIMPLIFICADO = 0.004
MIN_VERTICES = 3

ESCALA_MIN, ESCALA_MAX = 2, 8


def _leer_contorno(linea: str, lado: int) -> Optional[Tuple[int, List[Tuple[float, float]]]]:
    """
    Una línea de `contornos/*.txt` como (índice de clase, vértices en píxeles).

    El formato de YOLO para segmentación es `clase x1 y1 x2 y2 …` con las
    coordenadas relativas al tamaño de la imagen, así que acá se vuelven a
    multiplicar por el lado de la tesela.
    """
    partes = linea.split()
    if len(partes) < 1 + 2 * MIN_VERTICES or len(partes) % 2 == 0:
        return None
    try:
        indice = int(partes[0])
        valores = [float(v) for v in partes[1:]]
    except ValueError:
        return None
    vertices = [(valores[i] * lado, valores[i + 1] * lado) for i in range(0, len(valores), 2)]
    return indice, vertices


def _es_caja(vertices: Sequence[Tuple[float, float]]) -> bool:
    """
    Si el contorno son exactamente las cuatro esquinas de su propia caja.

    Es lo que `conversion_labelme.contorno_de_forma` genera para un `rectangle`,
    y el dato se pierde al guardar el contorno como texto de YOLO. Reconocerlo
    acá deja que el aporte derivado siga informando `contornos_de_caja`, que es
    el número que avisa que una parte del aporte no sirve para entrenar
    contornos. Un polígono dibujado a mano que dé exactamente las cuatro
    esquinas de su caja no se podría distinguir de uno, y no pasa en la práctica.
    """
    if len(vertices) != 4:
        return False
    xs = {round(x, 3) for x, _ in vertices}
    ys = {round(y, 3) for _, y in vertices}
    return len(xs) == 2 and len(ys) == 2


def _indexar_teselas(carpeta: Path) -> Tuple[Dict[Tuple[int, int], str], int]:
    """
    Ubica cada tesela del aporte en la grilla del ortomosaico.

    Devuelve {(columna, fila): nombre sin extensión} y el paso de la grilla. El
    paso se deduce de las posiciones (la menor distancia entre dos vecinas) y
    tiene que coincidir con el lado de las imágenes: este módulo pega teselas que
    no se solapan ni dejan hueco.
    """
    carpeta_imagenes = carpeta / "imagenes"
    posiciones: Dict[Tuple[int, int], str] = {}
    sin_posicion = 0
    lados = set()

    for ruta in sorted(carpeta_imagenes.iterdir()):
        if not ruta.is_file():
            continue
        coincidencia = PATRON_TESELA.search(ruta.stem)
        if not coincidencia:
            sin_posicion += 1
            continue
        with Image.open(ruta) as imagen:
            ancho, alto = imagen.size
        if ancho != alto:
            sin_posicion += 1
            continue
        lados.add(ancho)
        posiciones[(int(coincidencia.group(1)), int(coincidencia.group(2)))] = ruta.stem

    if len(posiciones) < 4:
        raise ErrorAporte(
            "Este aporte no sirve para generar escalas gruesas: hacen falta teselas que lleven "
            "su posición en el nombre, como 'tile_x19040_y34680', y acá no hay suficientes.",
            imagenes_sin_posicion=sin_posicion,
        )
    if len(lados) != 1:
        raise ErrorAporte(
            "Las teselas del aporte no miden todas lo mismo, así que no se pueden pegar.",
            lados_encontrados=sorted(lados),
        )

    lado = lados.pop()
    pasos = set()
    for eje in (0, 1):
        valores = sorted({p[eje] for p in posiciones})
        pasos.update(b - a for a, b in zip(valores, valores[1:]) if b > a)
    paso = min(pasos) if pasos else lado
    if paso != lado:
        raise ErrorAporte(
            f"Las teselas miden {lado} px pero la grilla avanza de {paso} px: se pegan teselas "
            "que no se solapan ni dejan hueco, y con esos números no cierra."
        )

    return {(x // paso, y // paso): nombre for (x, y), nombre in posiciones.items()}, paso


def _ventanas_completas(indice: Dict[Tuple[int, int], str], escala: int) -> List[Tuple[int, int]]:
    """
    Las ventanas de una escala, arrancando en múltiplos de la escala.

    No se solapan a propósito. Con paso de una tesela saldrían hasta escala²
    veces más ventanas, pero casi iguales entre sí, y el split de validación es
    al azar dentro del aporte (ver ensamblado): dos ventanas corridas una tesela
    comparten casi todo el terreno, y si una cae en entrenamiento y la otra en
    validación las métricas no miden nada.

    "Completa" es que estén las escala² teselas. Una ventana con un hueco
    tendría maleza sin etiquetar, y eso entrena peor que no tenerla.
    """
    return sorted(
        (c, f)
        for c, f in indice
        if c % escala == 0 and f % escala == 0
        and all((c + dc, f + df) in indice for dc in range(escala) for df in range(escala))
    )


def _simplificar(contorno: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    perimetro = cv2.arcLength(contorno, True)
    if perimetro <= 0:
        return None
    simplificado = cv2.approxPolyDP(contorno, TOLERANCIA_SIMPLIFICADO * perimetro, True)
    puntos = [(float(x), float(y)) for x, y in simplificado.reshape(-1, 2)]
    return puntos if len(puntos) >= MIN_VERTICES else None


def _unir_en_costuras(
    formas: List[Dict], lado_ventana: int, escala: int, paso: int, contadores: Counter
) -> List[Dict]:
    """
    Une las formas que quedaron partidas por una costura interna de la ventana.

    Una mancha a caballo de dos teselas se etiquetó dos veces, media en cada una,
    y al pegarlas siguen siendo dos formas: la ventana grande tendría dos manchas
    donde hay una, que es el mismo error que se quiere corregir. Las que tocan
    una costura se rasterizan juntas por clase y se les vuelve a trazar el
    contorno, que es lo que las fusiona.

    Las que no tocan ninguna costura pasan tal cual, para no perder precisión ni
    juntar dos manchas que el equipo dibujó aparte a propósito. Rasterizar
    resuelve la unión sin una biblioteca de geometría, y deja que findContours
    decida qué piezas no se tocan de verdad en vez de una regla de vecindad.
    """
    costuras = [i * paso for i in range(1, escala)]
    pegadas: Dict[int, List[Dict]] = {}
    sueltas: List[Dict] = []
    for forma in formas:
        toca = any(
            abs(coord - costura) <= MARGEN_COSTURA
            for x, y in forma["puntos"]
            for coord in (x, y)
            for costura in costuras
        )
        if toca:
            pegadas.setdefault(forma["clase"], []).append(forma)
        else:
            sueltas.append(forma)

    resultado = list(sueltas)
    for clase, grupo in pegadas.items():
        if len(grupo) == 1:
            resultado.extend(grupo)
            continue
        mascara = np.zeros((lado_ventana, lado_ventana), dtype=np.uint8)
        for forma in grupo:
            cv2.fillPoly(mascara, [np.array(forma["puntos"], dtype=np.int32).reshape(-1, 1, 2)], 255)
        mascara = cv2.morphologyEx(
            mascara, cv2.MORPH_CLOSE, np.ones((CIERRE_PX, CIERRE_PX), dtype=np.uint8)
        )
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        piezas = [p for p in (_simplificar(c) for c in contornos) if p is not None]
        if not piezas:
            # La unión no dejó nada usable: mejor las formas originales que ninguna
            resultado.extend(grupo)
            continue
        if len(piezas) < len(grupo):
            contadores["formas_unidas"] += len(grupo) - len(piezas)
        for puntos in piezas:
            # Salió de trazar la máscara, así que sigue el borde real de la
            # mancha aunque alguna de las partes viniera de un rectángulo
            resultado.append({"clase": clase, "puntos": puntos, "propio": True})

    return resultado


def _generar_ventana(
    origen: Path,
    indice: Dict[Tuple[int, int], str],
    columna: int,
    fila: int,
    escala: int,
    paso: int,
    destino: Path,
    contadores: Counter,
) -> None:
    """Pega una ventana, la reduce y escribe imagen, caja y contorno en formato YOLO."""
    lado_ventana = escala * paso
    lienzo = Image.new("RGB", (lado_ventana, lado_ventana))
    formas: List[Dict] = []

    for df in range(escala):
        for dc in range(escala):
            nombre = indice[(columna + dc, fila + df)]
            dx, dy = dc * paso, df * paso
            ruta_imagen = next(iter(sorted((origen / "imagenes").glob(f"{nombre}.*"))))
            with Image.open(ruta_imagen) as tesela:
                lienzo.paste(tesela.convert("RGB"), (dx, dy))

            ruta_contorno = origen / "contornos" / f"{nombre}.txt"
            if not ruta_contorno.is_file():
                continue
            for linea in ruta_contorno.read_text(encoding="utf-8").splitlines():
                if not linea.strip():
                    continue
                leido = _leer_contorno(linea, paso)
                if leido is None:
                    contadores["contornos_ilegibles"] += 1
                    continue
                clase, vertices = leido
                formas.append({
                    "clase": clase,
                    "puntos": [(x + dx, y + dy) for x, y in vertices],
                    "propio": not _es_caja(vertices),
                })

    formas = _unir_en_costuras(formas, lado_ventana, escala, paso, contadores)

    factor = LADO_SALIDA / lado_ventana
    nombre_salida = f"vent{escala}x_x{columna * paso}_y{fila * paso}"
    lineas_caja: List[str] = []
    lineas_contorno: List[str] = []

    for forma in formas:
        puntos = [(x * factor, y * factor) for x, y in forma["puntos"]]
        relativos = []
        for x, y in puntos:
            rx = min(1.0, max(0.0, x / LADO_SALIDA))
            ry = min(1.0, max(0.0, y / LADO_SALIDA))
            if not relativos or (round(rx, 6), round(ry, 6)) != relativos[-1]:
                relativos.append((round(rx, 6), round(ry, 6)))
        if len(relativos) > 1 and relativos[0] == relativos[-1]:
            relativos.pop()
        if len(set(relativos)) < MIN_VERTICES:
            # Al reducir la escala una mancha de pocos píxeles deja de encerrar área
            contadores["contornos_descartados"] += 1
            continue

        xs = [x for x, _ in relativos]
        ys = [y for _, y in relativos]
        clase = forma["clase"]
        lineas_caja.append(
            f"{clase} {(min(xs) + max(xs)) / 2:.6f} {(min(ys) + max(ys)) / 2:.6f} "
            f"{max(xs) - min(xs):.6f} {max(ys) - min(ys):.6f}"
        )
        lineas_contorno.append(f"{clase} " + " ".join(f"{x:.6f} {y:.6f}" for x, y in relativos))
        contadores[f"clase_{clase}"] += 1
        if not forma.get("propio", True):
            contadores["contornos_de_caja"] += 1

    lienzo.resize((LADO_SALIDA, LADO_SALIDA), Image.LANCZOS).save(
        destino / "imagenes" / f"{nombre_salida}.jpg", quality=CALIDAD_JPEG
    )
    for carpeta, lineas in (("etiquetas", lineas_caja), ("contornos", lineas_contorno)):
        texto = "\n".join(lineas)
        (destino / carpeta / f"{nombre_salida}.txt").write_text(
            texto + "\n" if texto else "", encoding="utf-8"
        )

    contadores["ventanas"] += 1
    if not lineas_contorno:
        contadores["ventanas_de_fondo"] += 1


def escalas_disponibles(dataset_id: str) -> Dict:
    """
    Cuántas ventanas completas saldrían de un aporte a cada escala, sin generarlas.

    Es lo que mira la web para ofrecer solo las escalas que dan algo: un aporte
    de teselas sueltas puede no tener ninguna ventana completa de 4×4.
    """
    carpeta = datasets.carpeta_de(dataset_id)
    if carpeta is None:
        return {"apto": False, "motivo": "El aporte no existe.", "escalas": {}}
    if not (carpeta / "contornos").is_dir():
        return {
            "apto": False,
            "motivo": "El aporte no tiene contornos: se subió antes de que existiera segmentación.",
            "escalas": {},
        }
    try:
        indice, paso = _indexar_teselas(carpeta)
    except ErrorAporte as e:
        return {"apto": False, "motivo": e.detalle["mensaje"], "escalas": {}}

    return {
        "apto": True,
        "motivo": None,
        "paso_px": paso,
        "escalas": {
            str(escala): len(_ventanas_completas(indice, escala))
            for escala in range(ESCALA_MIN, ESCALA_MAX + 1)
        },
    }


def generar_desde_dataset(dataset_id: str, escalas: Sequence[int]) -> List[Dict]:
    """
    Registra un aporte derivado por cada escala pedida y devuelve sus metas.

    Cada uno se arma en una carpeta temporal y se renombra al final, igual que
    una subida: un aporte a medias nunca aparece en el listado.
    """
    carpeta = datasets.carpeta_de(dataset_id)
    if carpeta is None:
        raise ErrorAporte("El aporte no existe.")
    meta_origen = datasets.leer_meta(dataset_id) or {}
    if not (carpeta / "contornos").is_dir():
        raise ErrorAporte(
            "El aporte no tiene contornos, así que no se puede derivar escala gruesa de él. "
            "Hay que volver a subir el ZIP: los polígonos siguen estando en sus .json de labelme."
        )

    clases = meta_origen.get("clases") or []
    indice, paso = _indexar_teselas(carpeta)
    creados: List[Dict] = []

    for escala in sorted(set(escalas)):
        if not ESCALA_MIN <= escala <= ESCALA_MAX:
            raise ErrorAporte(
                f"Escala {escala} fuera de rango: va de {ESCALA_MIN} a {ESCALA_MAX}. "
                "Una escala de 1 sería la tesela original."
            )
        ventanas = _ventanas_completas(indice, escala)
        if not ventanas:
            raise ErrorAporte(
                f"No hay ninguna ventana completa de {escala}×{escala} en este aporte: "
                f"hacen falta {escala * escala} teselas vecinas, todas etiquetadas.",
                escala=escala,
            )

        nuevo_id = uuid.uuid4().hex[:12]
        temporal = datasets.DATASETS_DIR / f".derivando-{nuevo_id}"
        try:
            for sub in ("imagenes", "etiquetas", "contornos"):
                (temporal / sub).mkdir(parents=True)
            contadores: Counter = Counter()
            for columna, fila in ventanas:
                _generar_ventana(carpeta, indice, columna, fila, escala, paso, temporal, contadores)

            por_clase = {
                clase: contadores.get(f"clase_{i}", 0) for i, clase in enumerate(clases)
            }
            total = sum(por_clase.values())
            meta = {
                "id": nuevo_id,
                "nombre": f"{meta_origen.get('nombre', dataset_id)} · ventanas {escala}×",
                "archivo_original": f"derivado de {dataset_id}",
                "fecha_creacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "clases": clases,
                # De qué aporte salió y con qué encuadre, que es lo que lo
                # distingue: las imágenes son las mismas teselas, pegadas.
                "derivado_de": dataset_id,
                "escala": escala,
                "lado_ventana_px": escala * paso,
                "total_imagenes": contadores["ventanas"],
                "total_anotaciones": total,
                "anotaciones_por_clase": por_clase,
                "imagenes_sin_objetos": contadores["ventanas_de_fondo"],
                # Por construcción no hay: una ventana a la que le falte una
                # tesela etiquetada no se genera.
                "imagenes_sin_anotar": 0,
                "formas_ignoradas": 0,
                "cajas_descartadas": 0,
                "total_contornos": total,
                "contornos_por_clase": dict(por_clase),
                "contornos_de_caja": contadores["contornos_de_caja"],
                "contornos_descartados": contadores["contornos_descartados"],
                "formas_unidas": contadores["formas_unidas"],
                "tiene_segmentacion": total > 0,
            }
            with open(temporal / "meta.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            temporal.rename(datasets.DATASETS_DIR / nuevo_id)
            creados.append(meta)
        except BaseException:
            shutil.rmtree(temporal, ignore_errors=True)
            raise

    return creados
