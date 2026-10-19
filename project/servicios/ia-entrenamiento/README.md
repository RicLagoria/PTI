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

## Cómo subir un aporte

Un ZIP con las imágenes y los `.json` que guarda labelme, en cualquier
estructura de carpetas. Al subirlo se convierte a YOLO y se rechaza **entero**
si algo no sirve, con el detalle de qué corregir:

- **Etiquetas:** se comparan por nombre contra `contratos/clases.json`,
  ignorando mayúsculas y espacios de más. Una etiqueta que no está en la lista
  rechaza el aporte; los índices que haya asignado cada labelme no se usan.
- **Formas:** rectángulos, polígonos y círculos se convierten a la caja que los
  encierra. Puntos y líneas se ignoran y se informan.
- **Imágenes:** se busca la de cada `.json` por su `imagePath`, o por el mismo
  nombre del `.json`, o embebida en `imageData`. Si mide distinto de lo que
  dice el `.json` se rechaza, porque las cajas quedarían corridas.
- **Fondos:** un `.json` sin formas entra como ejemplo negativo. Una imagen sin
  `.json` se ignora (puede ser un descuido) y se informa en el resultado.

En cada entrenamiento, el 20% de las imágenes de cada aporte va a validación.

## Semilla

`semilla/train-3/` es la corrida con la que se entrenó el modelo del MVP. Si
la API arranca con el registro vacío, la publica como primera versión y la
activa, para que `ia-inferencia` tenga modelo desde la primera instalación.
`clases.json` declara sus clases: si dejan de coincidir con el principio de la
lista canónica, no se siembra.

## Pesos de partida

`pesos_base` acepta `yolov8n.pt` o el nombre de una versión del registro, para
seguir entrenando un modelo anterior. Cualquier otro valor se rechaza: YOLO
abre los `.pt` con pickle, así que una ruta o URL libre permitiría ejecutar
código en el worker. `yolov8n.pt` se descarga de GitHub la primera vez que se
usa, así que el worker necesita salida a internet.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
