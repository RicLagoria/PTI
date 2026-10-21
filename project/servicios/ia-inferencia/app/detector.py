import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from ultralytics import YOLO


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


class FieldDetector:
    def __init__(self, model_path: Optional[str] = None):
        self.ruta_modelo = model_path or _obtener_ruta_modelo()
        self.version = os.environ.get("MODEL_VERSION", Path(self.ruta_modelo).parent.name if Path(self.ruta_modelo).exists() else "v1")
        if self.version in ("modelo", "weights", "."):
            self.version = "v1"

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
        Retorna: [{"id": id_opaco, "clase": str, "confianza": float, "box_local": [x1, y1, x2, y2]}]
        """
        if not self.model or not lista_tiles_con_id:
            return []

        imagenes = [item[1] for item in lista_tiles_con_id]
        resultados = self.model.predict(source=imagenes, conf=conf_threshold, save=False, verbose=False)

        detecciones = []
        for idx, res in enumerate(resultados):
            tile_id = lista_tiles_con_id[idx][0]

            for box in res.boxes:
                cls_id = int(box.cls[0])
                lx1, ly1, lx2, ly2 = box.xyxy[0].tolist()

                detecciones.append({
                    "id": tile_id,
                    "clase": self.model.names[cls_id],
                    "confianza": round(float(box.conf[0]) * 100, 2),
                    "box_local": [round(v, 1) for v in [lx1, ly1, lx2, ly2]]
                })

        return detecciones

