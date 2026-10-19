# ia-entrenamiento

Plano IA. Recibe aportes etiquetados, entrena y mantiene el registro de
versiones del modelo. Una sola imagen de Docker con dos comandos: la API y el
worker.

- `nucleo/` — código compartido por los dos: conversión de labelme a YOLO,
  remapeo de clases, cola de trabajos en disco y registro de modelos.
- `api/` — servidor FastAPI: datasets, entrenamientos (SSE) y modelos.
- `worker/` — toma trabajos de la cola, de a uno, y corre el entrenamiento
  (sale de `mvp/entrenador yolov8/train.py`).

Un entrenamiento publica una versión nueva pero nunca la activa: activar es un
paso explícito.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
