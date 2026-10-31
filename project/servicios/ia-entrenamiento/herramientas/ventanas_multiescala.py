"""
Arma imágenes de escala gruesa pegando teselas vecinas ya etiquetadas.

El modelo mira el campo a través de una tesela de 640 px, que en un ortomosaico
de 3,3 cm/px son unos 21 m: una mancha más grande que eso no entra en la imagen
y el modelo nunca la ve completa. En el dataset se nota — una de cada cuatro
manchas etiquetadas toca el borde de su tesela, y el percentil 95 del lado está
pegado al tamaño de la tesela, o sea que la distribución está cortada por el
encuadre, no por el campo.

Este script no pide reetiquetar nada. Pega N×N teselas vecinas en una sola
imagen, la reduce al lado de entrada del modelo y recompone las etiquetas
sumando el desplazamiento de cada tesela y multiplicando por el factor de
reducción. Una ventana de 4×4 cubre unos 89 m, así que la mancha que estaba
cortada aparece entera, y con eso el modelo puede aprender qué forma tiene.

Las manchas partidas por una costura interna (la misma mancha etiquetada como
dos formas, una en cada tesela) se unen: se rasterizan juntas y se les vuelve a
sacar el contorno. Sin ese paso la ventana grande tendría dos manchas pegadas
donde hay una, que es justamente el error que se quiere corregir.

Sale una carpeta por escala, para subir cada una como un aporte aparte: el split
de validación se hace dentro de cada aporte (ver nucleo/ensamblado.py), así cada
escala queda representada en validación.

Uso:
    python ventanas_multiescala.py --origen ~/Documents/PTI/dataset_tiles \
        --destino ~/Documents/PTI/dataset_tiles/ventanas --escalas 2,3,4
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo.clases import obtener_clases_canonicas  # noqa: E402
from nucleo.conversion_labelme import contorno_de_forma, normalizar_etiqueta  # noqa: E402

# El nombre con el que se recortaron las teselas lleva su posición en píxeles
# dentro del ortomosaico, y es lo único que dice cuáles son vecinas.
PATRON_TESELA = re.compile(r"tile_x(\d+)_y(\d+)", re.IGNORECASE)
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png")

# Lado de la imagen que se le entrega al modelo. Pegar N×N teselas y reducir a
# este tamaño es lo que "aleja la cámara": el mismo encuadre con N veces más campo.
LADO_SALIDA = 640

# Calidad del JPEG de salida. La misma con la que cliente-api codifica las
# teselas que le manda a ia-inferencia (ver analisis.py), para que el modelo
# entrene sobre el mismo nivel de compresión con el que después va a analizar.
CALIDAD_JPEG = 90

# Un vértice a menos de esto de una costura interna cuenta como pegado a ella y
# su forma entra en la unión. Las etiquetas se dibujaron tesela por tesela, así
# que las dos mitades de una mancha no coinciden al píxel sobre la costura.
MARGEN_COSTURA = 4
# Cierra huecos de hasta unos pocos píxeles entre las dos mitades antes de sacar
# el contorno; sin esto quedarían dos contornos pegados en vez de uno solo.
CIERRE_PX = 5

# Igual que en ia-inferencia: el contorno de una máscara trae cientos de
# vértices casi colineales, y la tolerancia va relativa al perímetro para que
# una mancha chica no termine convertida en un triángulo.
TOLERANCIA_SIMPLIFICADO = 0.004
MIN_VERTICES = 3

VERSION_LABELME = "5.10.1"


def resolver_clase(etiqueta: str, canonicas: Sequence[str]) -> Optional[str]:
    """
    La clase canónica de una etiqueta de labelme, o None si hay que descartarla.

    Un typo de una clase canónica se corrige y una clase retirada se descarta,
    que es la misma regla con la que se venían armando los ZIP a mano: si al
    sacarle lo que no son letras la etiqueta coincide con una canónica, era un
    typo (`maleza}`); si no, es una clase que salió de la taxonomía (`camino`,
    `arbolada`) y entrenar con ella haría rechazar el aporte entero.
    """
    normal = normalizar_etiqueta(etiqueta)
    if normal in canonicas:
        return normal
    solo_letras = re.sub(r"[^a-záéíóúüñ]", "", normal)
    return solo_letras if solo_letras in canonicas else None


def indexar_teselas(origen: Path) -> Tuple[Dict[Tuple[int, int], Tuple[Path, Path]], int, Dict]:
    """
    Ubica cada tesela etiquetada en la grilla del ortomosaico.

    Devuelve el índice {(columna, fila): (imagen, json)}, el paso de la grilla en
    píxeles y un resumen. Una tesela sin JSON queda afuera a propósito: no se
    sabe si no tiene maleza o si nadie la etiquetó, y meterla en una ventana le
    enseñaría al modelo que la maleza que hay ahí es fondo.
    """
    con_json: Dict[Tuple[int, int], Path] = {}
    posiciones: List[Tuple[int, int]] = []
    sin_json = 0
    total = 0

    for ruta in sorted(origen.rglob("*")):
        if ruta.suffix.lower() not in EXTENSIONES_IMAGEN:
            continue
        coincidencia = PATRON_TESELA.search(ruta.name)
        if not coincidencia:
            continue
        total += 1
        ruta_json = ruta.with_suffix(".json")
        if not ruta_json.is_file():
            sin_json += 1
            continue
        x, y = int(coincidencia.group(1)), int(coincidencia.group(2))
        posiciones.append((x, y))
        con_json[(x, y)] = ruta

    if len(posiciones) < 2:
        raise SystemExit(f"No hay teselas etiquetadas suficientes en {origen}")

    paso = _deducir_paso(posiciones)
    lado = _lado_de_tesela(next(iter(con_json.values())))
    if lado != paso:
        raise SystemExit(
            f"Las teselas miden {lado} px pero la grilla avanza de {paso} px: este script "
            "pega teselas que no se solapan ni dejan hueco, y con esos números no cierra."
        )

    indice: Dict[Tuple[int, int], Tuple[Path, Path]] = {}
    desalineadas = 0
    for (x, y), imagen in con_json.items():
        if x % paso or y % paso:
            desalineadas += 1
            continue
        indice[(x // paso, y // paso)] = (imagen, imagen.with_suffix(".json"))

    resumen = {
        "teselas_encontradas": total,
        "teselas_sin_json": sin_json,
        "teselas_desalineadas": desalineadas,
        "teselas_usables": len(indice),
        "paso_px": paso,
    }
    return indice, paso, resumen


def _deducir_paso(posiciones: Sequence[Tuple[int, int]]) -> int:
    """Paso de la grilla: la menor distancia entre dos teselas vecinas en x o en y."""
    pasos = set()
    for eje in (0, 1):
        valores = sorted({p[eje] for p in posiciones})
        pasos.update(b - a for a, b in zip(valores, valores[1:]) if b > a)
    if not pasos:
        raise SystemExit("No se pudo deducir el paso de la grilla de teselas.")
    return min(pasos)


def _lado_de_tesela(ruta: Path) -> int:
    with Image.open(ruta) as imagen:
        ancho, alto = imagen.size
    if ancho != alto:
        raise SystemExit(f"La tesela {ruta.name} no es cuadrada ({ancho}x{alto}).")
    return ancho


def formas_de_tesela(
    ruta_json: Path, dx: int, dy: int, canonicas: Sequence[str], contadores: Counter
) -> List[Dict]:
    """
    Las formas de una tesela como contornos en coordenadas de la ventana.

    Cada forma se reduce a su contorno (un `rectangle` o un `circle` también
    tienen uno, ver nucleo/conversion_labelme.contorno_de_forma) y se la corre al
    lugar que la tesela ocupa dentro de la ventana.
    """
    try:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        contadores["json_ilegibles"] += 1
        return []

    formas = []
    for forma in datos.get("shapes") or []:
        clase = resolver_clase(forma.get("label", ""), canonicas)
        if clase is None:
            contadores["etiquetas_descartadas"] += 1
            continue
        if normalizar_etiqueta(forma.get("label", "")) != clase:
            contadores["etiquetas_corregidas"] += 1
        contorno = contorno_de_forma(forma)
        if contorno is None:
            contadores["formas_sin_contorno"] += 1
            continue
        vertices, propio = contorno
        if not propio:
            contadores["contornos_de_caja"] += 1
        formas.append({
            "clase": clase,
            "puntos": [(x + dx, y + dy) for x, y in vertices],
            # Si el contorno es el que se dibujó o uno sacado de la caja de un
            # `rectangle`. Se arrastra hasta la salida para no perder el dato.
            "propio": propio,
        })
    return formas


def _toca_alguna(puntos: Sequence[Tuple[float, float]], lineas_x, lineas_y) -> bool:
    for x, y in puntos:
        if any(abs(x - linea) <= MARGEN_COSTURA for linea in lineas_x):
            return True
        if any(abs(y - linea) <= MARGEN_COSTURA for linea in lineas_y):
            return True
    return False


def _simplificar(contorno: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    perimetro = cv2.arcLength(contorno, True)
    if perimetro <= 0:
        return None
    simplificado = cv2.approxPolyDP(contorno, TOLERANCIA_SIMPLIFICADO * perimetro, True)
    puntos = [(float(x), float(y)) for x, y in simplificado.reshape(-1, 2)]
    return puntos if len(puntos) >= MIN_VERTICES else None


def unir_en_costuras(
    formas: List[Dict], lado_ventana: int, escala: int, paso: int, contadores: Counter
) -> List[Dict]:
    """
    Une las formas que quedaron partidas por una costura interna de la ventana.

    Una mancha a caballo de dos teselas se etiquetó dos veces, una mitad en cada
    tesela, y al pegarlas siguen siendo dos formas que se tocan. Las que están
    pegadas a una costura se rasterizan juntas por clase y se les vuelve a sacar
    el contorno, que es lo que las fusiona; las demás pasan tal cual, para no
    perder precisión ni juntar dos manchas que el equipo dibujó aparte a propósito.

    Rasterizar y volver a trazar lo resuelve sin una biblioteca de geometría, y
    de paso separa solo las piezas que de verdad no se tocan: lo decide
    findContours sobre la máscara, no una regla de vecindad escrita acá.
    """
    costuras = [i * paso for i in range(1, escala)]
    pegadas: Dict[str, List[Dict]] = {}
    sueltas: List[Dict] = []
    for forma in formas:
        if costuras and _toca_alguna(forma["puntos"], costuras, costuras):
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
            puntos = np.array(forma["puntos"], dtype=np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(mascara, [puntos], 255)
        nucleo = np.ones((CIERRE_PX, CIERRE_PX), dtype=np.uint8)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, nucleo)

        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        piezas = [p for p in (_simplificar(c) for c in contornos) if p is not None]
        if not piezas:
            # La unión no dejó nada usable: mejor las formas originales que ninguna
            resultado.extend(grupo)
            continue
        if len(piezas) < len(grupo):
            contadores["formas_unidas"] += len(grupo) - len(piezas)
        for puntos in piezas:
            # El contorno salió de trazar la máscara, así que sigue el borde real
            # de la mancha aunque alguna de las partes viniera de un rectángulo
            resultado.append({"clase": clase, "puntos": puntos, "propio": True})

    return resultado


def generar_ventana(
    indice: Dict[Tuple[int, int], Tuple[Path, Path]],
    columna: int,
    fila: int,
    escala: int,
    paso: int,
    canonicas: Sequence[str],
    destino: Path,
    contadores: Counter,
) -> bool:
    """Pega una ventana de escala×escala teselas, la reduce y escribe imagen + JSON."""
    lado_ventana = escala * paso
    lienzo = Image.new("RGB", (lado_ventana, lado_ventana))
    formas: List[Dict] = []

    for df in range(escala):
        for dc in range(escala):
            ruta_imagen, ruta_json = indice[(columna + dc, fila + df)]
            with Image.open(ruta_imagen) as tesela:
                if tesela.size != (paso, paso):
                    contadores["ventanas_con_tesela_de_otro_tamano"] += 1
                    return False
                lienzo.paste(tesela.convert("RGB"), (dc * paso, df * paso))
            formas += formas_de_tesela(ruta_json, dc * paso, df * paso, canonicas, contadores)

    formas = unir_en_costuras(formas, lado_ventana, escala, paso, contadores)

    factor = LADO_SALIDA / lado_ventana
    nombre = f"vent{escala}x_x{columna * paso}_y{fila * paso}"
    salida_shapes = []
    for forma in formas:
        puntos = [[round(x * factor, 2), round(y * factor, 2)] for x, y in forma["puntos"]]
        if len({tuple(p) for p in puntos}) < MIN_VERTICES:
            # Al reducir la escala una mancha de pocos píxeles deja de encerrar área
            contadores["formas_perdidas_al_reducir"] += 1
            continue
        if forma.get("propio", True):
            tipo, puntos_salida = "polygon", puntos
        else:
            # Venía de un `rectangle` y no se unió con nada, así que sigue siendo
            # la caja de la etiqueta y no la forma de la mancha. Se escribe como
            # rectángulo, no como polígono, para que el resumen del aporte lo
            # siga contando en `contornos_de_caja`: es el número que avisa que
            # una parte del aporte no sirve para entrenar contornos. Escribirlo
            # como polígono lo haría pasar por un contorno dibujado a mano.
            xs = [p[0] for p in puntos]
            ys = [p[1] for p in puntos]
            tipo = "rectangle"
            puntos_salida = [[min(xs), min(ys)], [max(xs), max(ys)]]
        salida_shapes.append({
            "label": forma["clase"],
            "points": puntos_salida,
            "group_id": None,
            "description": "",
            "shape_type": tipo,
            "flags": {},
            "mask": None,
        })
        if _toca_borde(puntos):
            contadores["formas_que_tocan_el_borde"] += 1
        contadores[f"formas_{forma['clase']}"] += 1

    lienzo.resize((LADO_SALIDA, LADO_SALIDA), Image.LANCZOS).save(
        destino / f"{nombre}.jpg", quality=CALIDAD_JPEG
    )
    (destino / f"{nombre}.json").write_text(json.dumps({
        "version": VERSION_LABELME,
        "flags": {},
        "shapes": salida_shapes,
        "imagePath": f"{nombre}.jpg",
        "imageData": None,
        "imageHeight": LADO_SALIDA,
        "imageWidth": LADO_SALIDA,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    contadores["ventanas"] += 1
    if not salida_shapes:
        contadores["ventanas_de_fondo"] += 1
    return True


def _toca_borde(puntos: Sequence[Sequence[float]]) -> bool:
    """Si la forma llega al borde de la ventana, o sea que sigue cortada a esta escala."""
    return any(
        x <= MARGEN_COSTURA or y <= MARGEN_COSTURA
        or x >= LADO_SALIDA - MARGEN_COSTURA or y >= LADO_SALIDA - MARGEN_COSTURA
        for x, y in puntos
    )


def ventanas_de_escala(indice, escala: int) -> List[Tuple[int, int]]:
    """
    Las ventanas completas de una escala, arrancando en múltiplos de la escala.

    Las ventanas de una misma escala no se solapan a propósito. Con paso de una
    tesela saldrían hasta escala² veces más ventanas, pero casi iguales entre sí,
    y el split de validación es al azar dentro del aporte (nucleo/ensamblado.py):
    dos ventanas corridas una tesela comparten casi todo el terreno, y si una cae
    en entrenamiento y la otra en validación las métricas no miden nada.

    "Completa" es que estén las escala² teselas y todas etiquetadas. Una ventana
    con un hueco tendría maleza sin etiquetar, que entrena peor que no tenerla.
    """
    return sorted(
        (c, f)
        for c, f in indice
        if c % escala == 0 and f % escala == 0
        and all((c + dc, f + df) in indice for dc in range(escala) for df in range(escala))
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--origen", required=True, type=Path, help="carpeta con los lotes de teselas etiquetadas")
    parser.add_argument("--destino", required=True, type=Path, help="carpeta donde escribir un aporte por escala")
    parser.add_argument("--escalas", default="2,3,4", help="cuántas teselas por lado de cada ventana (coma)")
    args = parser.parse_args()

    escalas = sorted({int(e) for e in args.escalas.split(",") if e.strip()})
    if any(e < 2 for e in escalas):
        raise SystemExit("Una escala de 1 sería la tesela original: las escalas arrancan en 2.")

    canonicas = obtener_clases_canonicas()
    indice, paso, resumen = indexar_teselas(args.origen)
    print(f"clases canónicas: {canonicas}")
    print("  ".join(f"{k}={v}" for k, v in resumen.items()))

    for escala in escalas:
        ventanas = ventanas_de_escala(indice, escala)
        destino = args.destino / f"ventanas-{escala}x"
        destino.mkdir(parents=True, exist_ok=True)
        contadores: Counter = Counter()
        for columna, fila in ventanas:
            generar_ventana(indice, columna, fila, escala, paso, canonicas, destino, contadores)

        lado_ventana = escala * paso
        print(
            f"\n[{escala}x] {contadores['ventanas']} ventanas de {lado_ventana} px "
            f"reducidas a {LADO_SALIDA} -> {destino}"
        )
        for clave in sorted(contadores):
            if clave != "ventanas":
                print(f"       {clave}: {contadores[clave]}")


if __name__ == "__main__":
    main()
