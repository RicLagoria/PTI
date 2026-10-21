"""
Evaluación numérica de un modelo recién entrenado sobre sus imágenes de validación.

Ultralytics ya deja la matriz de confusión y las curvas como PNG; esto guarda los
números (evaluacion.json) para que entrenador-web los dibuje y los compare.

Ojo al leer los resultados: son las mismas imágenes con las que se eligió la
mejor época, así que la estimación es algo optimista.
"""
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
from ultralytics import YOLO
from ultralytics.utils.metrics import smooth

# Puntos de las curvas contra la confianza que se guardan (Ultralytics usa 1000)
PUNTOS_CURVA = 101
# IoU mínimo para que una predicción cuente como acierto en la matriz (fijo en Ultralytics)
IOU_MATRIZ = 0.45
UMBRAL_POR_DEFECTO = 0.25
# Por debajo de este F1 el modelo prácticamente no acierta y el "mejor umbral" es ruido
F1_MINIMO_PARA_RECOMENDAR = 0.05


def _redondear(valor) -> Optional[float]:
    return None if valor is None else round(float(valor), 4)


def _muestrear(valores, cantidad: int) -> List[float]:
    """Toma `cantidad` puntos equiespaciados de la curva, incluidos el primero y el último."""
    indices = np.linspace(0, len(valores) - 1, cantidad).round().astype(int)
    return [_redondear(valores[i]) for i in indices]


def evaluar_modelo(
    pesos: str, ruta_yaml: Path, imgsz: int, carpeta: Path, clases: List[str],
    al_avanzar: Optional[Callable[[], None]] = None,
) -> Dict:
    """
    Corre la validación de `pesos` y devuelve el contenido de evaluacion.json.
    `al_avanzar` se llama en cada lote: el worker lo usa para seguir dando latido.
    """
    comunes = dict(
        data=str(ruta_yaml), imgsz=imgsz, batch=2, device="cpu", workers=2, split="val",
        plots=False, verbose=False, project=str(carpeta), name="evaluacion", exist_ok=True,
    )
    modelo = YOLO(pesos)
    if al_avanzar:
        modelo.add_callback("on_val_batch_end", lambda validador: al_avanzar())

    # 1ª pasada, sin umbral: el mAP se calcula sobre todas las predicciones
    metricas = modelo.val(**comunes)
    caja = metricas.box

    # Umbral que maximiza el F1 promedio entre clases, con el mismo suavizado que usa
    # Ultralytics para reportar precisión y recall. Es el que conviene usar al analizar.
    umbral = None
    curvas = None
    if getattr(caja, "f1_curve", None) is not None and len(caja.f1_curve):
        f1_medio = caja.f1_curve.mean(0)
        f1_suave = smooth(f1_medio, 0.1)
        if f1_suave.max() >= F1_MINIMO_PARA_RECOMENDAR:
            umbral = _redondear(caja.px[f1_suave.argmax()])
        curvas = {
            "confianza": _muestrear(caja.px, PUNTOS_CURVA),
            "precision": _muestrear(caja.p_curve.mean(0), PUNTOS_CURVA),
            "recall": _muestrear(caja.r_curve.mean(0), PUNTOS_CURVA),
            "f1": _muestrear(f1_medio, PUNTOS_CURVA),
        }

    # Por clase: las que no tienen instancias en validación no aparecen en
    # ap_class_index, y se informan con 0 instancias y sin métricas
    instancias = [int(n) for n in (metricas.nt_per_class if metricas.nt_per_class is not None else [0] * len(clases))]
    posicion = {int(c): i for i, c in enumerate(caja.ap_class_index)}
    por_clase = []
    for indice, clase in enumerate(clases):
        i = posicion.get(indice)
        por_clase.append({
            "clase": clase,
            "instancias": instancias[indice] if indice < len(instancias) else 0,
            "precision": _redondear(caja.p[i]) if i is not None else None,
            "recall": _redondear(caja.r[i]) if i is not None else None,
            "map50": _redondear(caja.ap50[i]) if i is not None else None,
            "map50_95": _redondear(caja.ap[i]) if i is not None else None,
        })

    # 2ª pasada, con el umbral recomendado: la matriz depende del umbral y tiene
    # que reflejar cómo se va a comportar el modelo en el análisis. Ultralytics la
    # guarda como matriz[predicho][real]; se traspone a filas = clase real.
    # Ultralytics solo llena la matriz si la validación corre con plots=True.
    umbral_matriz = umbral if umbral is not None else UMBRAL_POR_DEFECTO
    matriz = modelo.val(**{**comunes, "plots": True}, conf=umbral_matriz).confusion_matrix.matrix
    filas_reales = [[int(matriz[predicho][real]) for predicho in range(len(matriz))] for real in range(len(matriz))]

    return {
        "conjunto": "validacion",
        "metricas": {
            "precision": _redondear(caja.mp),
            "recall": _redondear(caja.mr),
            "map50": _redondear(caja.map50),
            "map50_95": _redondear(caja.map),
        },
        "umbral_recomendado": umbral,
        "por_clase": por_clase,
        "matriz_confusion": {
            "umbral": umbral_matriz,
            "iou": IOU_MATRIZ,
            # La última fila y columna es el fondo: real fondo = falsa alarma,
            # predicho fondo = objeto que el modelo no vio
            "etiquetas": [*clases, "fondo"],
            "filas_reales": filas_reales,
        },
        "curvas_confianza": curvas,
    }
