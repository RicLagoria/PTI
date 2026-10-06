from ultralytics import YOLO

class FieldDetector:
    def __init__(self, model_path="runs/detect/train-2/weights/best.pt", conf_threshold=0.15):
        self.model = YOLO(model_path)
        self.conf = conf_threshold

    def procesar_lote_celdas(self, lista_tiles_con_meta):
        """
        lista_tiles_con_meta: Lista de tuplas (celda_meta, imagen_bgr)
        Retorna los metadatos de las cajas detectadas con coordenadas globales.
        """
        if not lista_tiles_con_meta:
            return []

        imagenes = [item[1] for item in lista_tiles_con_meta]
        resultados = self.model.predict(source=imagenes, conf=self.conf, save=False, verbose=False)

        detecciones_globales = []
        for idx, res in enumerate(resultados):
            meta = lista_tiles_con_meta[idx][0]
            offset_x = meta["x"]
            offset_y = meta["y"]

            for box in res.boxes:
                cls_id = int(box.cls[0])
                lx1, ly1, lx2, ly2 = box.xyxy[0].tolist()

                # Proyección global sobre el ortomosaico entero
                gx1 = offset_x + lx1
                gy1 = offset_y + ly1
                gx2 = offset_x + lx2
                gy2 = offset_y + ly2

                detecciones_globales.append({
                    "fila": meta["fila"],
                    "col": meta["col"],
                    "clase": self.model.names[cls_id],
                    "confianza": round(float(box.conf[0]) * 100, 2),
                    "box_local": [round(v, 1) for v in [lx1, ly1, lx2, ly2]],
                    "box_global_px": [round(v, 1) for v in [gx1, gy1, gx2, gy2]],
                    "gps_centro": {"lat": meta["lat"], "lon": meta["lon"]}
                })

        return detecciones_globales