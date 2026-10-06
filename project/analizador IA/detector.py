from ultralytics import YOLO

class FieldDetector:
    def __init__(self, model_path="runs/detect/train-2/weights/best.pt", conf_threshold=0.15):
        self.model = YOLO(model_path)
        self.conf = conf_threshold

    def predecir_tile(self, tile_bgr):
        results = self.model.predict(source=tile_bgr, conf=self.conf, save=False, verbose=False)
        detecciones = []
        img_anotada = tile_bgr

        for r in results:
            img_anotada = r.plot()
            for box in r.boxes:
                cls_id = int(box.cls[0])
                detecciones.append({
                    "clase": self.model.names[cls_id],
                    "confianza": float(box.conf[0]) * 100,
                    "xyxy": box.xyxy[0].tolist()
                })

        return detecciones, img_anotada