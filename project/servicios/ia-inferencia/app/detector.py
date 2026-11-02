import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np
from ultralytics import YOLO

# Una máscara de YOLO sale como un contorno de cientos de vértices, de los que
# casi todos están sobre la misma recta: son los píxeles del borde. Se simplifica
# con Douglas-Peucker antes de devolverla, porque el contorno viaja hasta el
# navegador y se guarda en la base. La tolerancia es relativa al perímetro, así
# una mancha grande no queda angulosa ni una chica se convierte en un triángulo.
TOLERANCIA_SIMPLIFICADO = 0.004
# Por si el simplificado no alcanza con un contorno muy enrulado
MAX_VERTICES = 80
# Menos que esto no encierra área y no sirve como polígono
MIN_VERTICES = 3


def _obtener_ruta_modelo() -> str:
    env_path = os.environ.get("MODEL_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # Posibles ubicaciones tanto en desarrollo local como en contenedores
    candidatos = [
        Path("/data/modelos/activo/best.pt"),
        Path("/data/modelo/best.pt"),
        Path("datos/modelos/activo/best.pt"),
        Path("../datos/modelos/activo/best.pt"),
        Path("../../datos/modelos/activo/best.pt"),
        Path("../../../datos/modelos/activo/best.pt"),
        Path("project/mvp/data/modelo/best.pt"),
        Path("../mvp/data/modelo/best.pt"),
        Path("../../mvp/data/modelo/best.pt"),
        Path("../../../mvp/data/modelo/best.pt"),
        Path("data/modelo/best.pt"),
    ]
    for c in candidatos:
        if c.exists():
            return str(c.resolve())

    return env_path or "data/modelo/best.pt"


def _obtener_version(ruta_modelo: Path) -> str:
    """
    Nombre de la versión cargada. ia-entrenamiento, al activar una versión, deja su
    nombre en version.txt junto a los pesos (datos/modelos/activo/); sin él, el nombre
    de la carpeta sería siempre "activo" y no se sabría con qué modelo se analizó.
    """
    if os.environ.get("MODEL_VERSION"):
        return os.environ["MODEL_VERSION"]
    archivo_version = ruta_modelo.parent / "version.txt"
    if archivo_version.is_file():
        version = archivo_version.read_text(encoding="utf-8").strip()
        if version:
            return version
    if not ruta_modelo.exists() or ruta_modelo.parent.name in ("modelo", "weights", "activo", "."):
        return "v1"
    return ruta_modelo.parent.name


def _simplificar_contorno(puntos: np.ndarray) -> Optional[List[List[float]]]:
    """
    Pasa el contorno de una máscara a una lista de vértices [[x, y], ...] con los
    puntos justos. None si no encierra área (puede pasar con una máscara de unos
    pocos píxeles: existe la detección, pero su contorno es una línea).
    """
    if puntos is None or len(puntos) < MIN_VERTICES:
        return None

    contorno = np.asarray(puntos, dtype=np.float32).reshape(-1, 1, 2)
    perimetro = cv2.arcLength(contorno, True)
    tolerancia = TOLERANCIA_SIMPLIFICADO * perimetro
    simplificado = cv2.approxPolyDP(contorno, tolerancia, True)
    # Con un contorno muy irregular Douglas-Peucker puede dejar muchos vértices:
    # se insiste con el doble de tolerancia hasta bajar del tope
    while len(simplificado) > MAX_VERTICES and tolerancia < perimetro:
        tolerancia *= 2
        simplificado = cv2.approxPolyDP(contorno, tolerancia, True)

    vertices = [[round(float(x), 1), round(float(y), 1)] for x, y in simplificado.reshape(-1, 2)]
    return vertices if len(vertices) >= MIN_VERTICES else None


class FieldDetector:
    def __init__(self, model_path: Optional[str] = None):
        self.ruta_modelo = model_path or _obtener_ruta_modelo()
        self.version = _obtener_version(Path(self.ruta_modelo))

        if Path(self.ruta_modelo).exists():
            self.model = YOLO(self.ruta_modelo)
            # imgsz por defecto del modelo o 640
            self.imgsz = getattr(self.model.overrides, "get", lambda k, d: d)("imgsz", 640) if hasattr(self.model, "overrides") else 640
        else:
            self.model = None
            self.imgsz = 640

    def esta_disponible(self) -> bool:
        return self.model is not None

    def obtener_info(self) -> Dict[str, Any]:
        if not self.model:
            return {
                "version": self.version,
                "clases": ["maleza", "falla"],
                "imgsz": self.imgsz,
                "tarea": "detect",
                "metricas": {},
                "disponible": False
            }

        nombres_clases = self.model.names
        if isinstance(nombres_clases, dict):
            clases = [nombres_clases[i] for i in sorted(nombres_clases.keys())]
        else:
            clases = list(nombres_clases)

        return {
            "version": self.version,
            "clases": clases,
            "imgsz": self.imgsz,
            # "segment" si los pesos activos devuelven contornos, "detect" si solo
            # cajas. Sale del .pt, no de una configuración: activar otra versión
            # cambia esto sin tocar nada. cliente-api lo usa para saber si esperar
            # contornos, y la web para dibujar polígonos o marcadores.
            "tarea": getattr(self.model, "task", "detect") or "detect",
            "metricas": {},
            "disponible": True
        }

    def procesar_lote(
        self,
        lista_tiles_con_id: List[Tuple[str, np.ndarray]],
        conf_threshold: float = 0.10
    ) -> List[Dict[str, Any]]:
        """
        Infiere sobre un lote de imágenes y retorna detecciones en píxeles locales.
        lista_tiles_con_id: [(id_opaco, imagen_bgr), ...]
        Retorna: [{"id": id_opaco, "clase": str, "confianza": float,
                   "box_local": [x1, y1, x2, y2],
                   "contorno_local": [[x, y], ...] (solo con un modelo segment)}]

        El contorno es el aporte de un modelo de segmentación: el borde de la
        mancha, no el rectángulo que la encierra. Va junto a la caja y no en vez
        de ella, porque la caja la sigue usando quien solo quiere un punto (el
        centro de la detección) y porque un modelo detect no tiene contorno.
        Este servicio sigue sin saber de geografía: son píxeles de la tesela que
        recibió, y cliente-api los lleva a coordenadas.
        """
        if not self.model or not lista_tiles_con_id:
            return []

        imagenes = [item[1] for item in lista_tiles_con_id]
        resultados = self.model.predict(source=imagenes, conf=conf_threshold, save=False, verbose=False)

        detecciones = []
        for idx, res in enumerate(resultados):
            tile_id = lista_tiles_con_id[idx][0]
            # En un modelo segment, masks.xy trae un contorno por caja y en el
            # mismo orden, ya escalado a los píxeles de la tesela. En uno detect
            # masks es None.
            contornos = getattr(res.masks, "xy", None) if res.masks is not None else None

            for i, box in enumerate(res.boxes):
                cls_id = int(box.cls[0])
                lx1, ly1, lx2, ly2 = box.xyxy[0].tolist()

                deteccion = {
                    "id": tile_id,
                    "clase": self.model.names[cls_id],
                    "confianza": round(float(box.conf[0]) * 100, 2),
                    "box_local": [round(v, 1) for v in [lx1, ly1, lx2, ly2]]
                }

                if contornos is not None and i < len(contornos):
                    vertices = _simplificar_contorno(contornos[i])
                    if vertices is not None:
                        deteccion["contorno_local"] = vertices

                detecciones.append(deteccion)

        return detecciones

