from ultralytics import YOLO

def main():
    # 1. Cargar el modelo base preentrenado de segmentación
    model = YOLO("yolov8n.pt")

    # 2. Entrenar el modelo
    results = model.train(
        data="Dataset/dataset.yaml",  # Ruta a tu dataset.yaml
        epochs=50,          # 50 épocas es suficiente para probar el flujo
        imgsz=640,          # Tamaño estándar
        batch=2,            # Batch pequeño para tu cantidad de datos (o batch=4)
        device="cpu",       # Indicamos explícitamente CPU
        workers=2           # 2 hilos para no saturar los núcleos de tu i3
    )

if __name__ == "__main__":
    main()