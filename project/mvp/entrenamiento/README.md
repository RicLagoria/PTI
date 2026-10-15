# Entrenamiento de Modelo YOLOv8

Este módulo contiene el script para entrenar o reentrenar el modelo de detección de malezas para AgroVision utilizando la biblioteca [Ultralytics YOLO](https://docs.ultralytics.com/).

## Estructura requerida

Para ejecutar el entrenamiento con `train.py`, es necesario contar con un dataset anotado en formato YOLO y referenciado en un archivo `dataset.yaml`:

```
entrenamiento/
├── train.py
├── Dataset/
│   ├── dataset.yaml
│   ├── images/
│   │   ├── train/
│   │   └── val/
│   └── labels/
│       ├── train/
│       └── val/
```

## Uso

1. Instalar las dependencias (ultralytics, torch, torchvision):
   ```bash
   pip install ultralytics torch torchvision
   ```

2. Ejecutar el script:
   ```bash
   python train.py
   ```

3. Al finalizar, el mejor checkpoint se generará en `runs/detect/.../weights/best.pt`. Luego, copiar dicho archivo a `data/modelo/best.pt` para que sea utilizado por el backend y Docker Compose.

