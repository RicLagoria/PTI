# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Proyecto Tecnológico Integrador (2026): aplicación web que analiza ortomosaicos GeoTIFF georreferenciados de campos con un modelo YOLOv8 para detectar malezas/objetos y ubicarlos en un mapa. El código, los comentarios y los identificadores están en español; mantener esa convención.

**El código vigente es `mvp/`.** El resto de las carpetas son iteraciones anteriores o experimentos y no deben tomarse como referencia salvo pedido explícito:

- `front+back/` — versión previa del mismo backend/frontend (`detector.py` y `geo.py` idénticos a los del MVP; `server.py`, `predict.py` e `index.html` divergen).
- `analizador IA/` — prototipo de línea de comandos sin servidor.
- `entrenar ia/` — entorno de entrenamiento con el dataset, los `runs/` de Ultralytics y los pesos entrenados (`runs/detect/train-2/weights/best.pt`). Su `predict.py` es una GUI Tkinter que ubica fotos sueltas por GPS EXIF, no por GeoTIFF.
- `ejemplos de modelos/` — pruebas con TensorFlow/transformers (Python 3.12, entorno distinto).

## Comandos

Python 3.9.13. No hay tests, linter ni build configurados.

```bash
# Todo el MVP con Docker (front + back detrás de nginx): http://localhost:8080
# Requiere los pesos en mvp/data/modelo/best.pt (copiarlos de "entrenar ia/runs/detect/train-2/weights/")
cd mvp && docker compose up --build

# Dependencias para correr el backend sin Docker
# ("mvp/requerimientos .txt" es la lista original y no sirve con pip: contiene la línea "Python 3.9.13")
pip install -r mvp/back/requirements.txt

# Backend (FastAPI) — debe ejecutarse desde mvp/back, ver "Rutas relativas"
cd mvp/back && uvicorn server:app --reload --port 8000

# Pipeline de detección sin servidor (escribe detecciones_campo.json; espera "El Azul_COG.tif" en el cwd)
cd mvp/back && python predict.py

# Frontend sin Docker: HTML estático sin build; abrir mvp/front/index.html en el navegador

# Entrenamiento (desde la carpeta que contiene Dataset/ y yolov8n.pt)
cd "entrenar ia" && python train.py
```

El `requerimientos.txt` de la raíz corresponde al entorno de entrenamiento/etiquetado (labelme, labelme2yolo, etc.), no al servidor web.

### Rutas y variables de entorno

Sin Docker, el backend resuelve todo contra el directorio de trabajo; `docker-compose.yml` apunta las tres variables al volumen `mvp/data/` (ignorado por git, montado en `/data`).

- `MODEL_PATH`: pesos de YOLO. Por defecto `runs/detect/train-2/weights/best.pt`, que no existe en `mvp/back/`; los pesos reales están en `entrenar ia/runs/detect/train-2/weights/`.
- `UPLOAD_DIR`: imágenes subidas. Por defecto `data/imagenes/`.
- `MAX_UPLOAD_MB`: tope de subida (8192 por defecto).

Hay un ortomosaico de prueba en `img/ortomosaico/El Azul_COG.tif` (1,3 GB, EPSG:4326, ignorado por git).

## Arquitectura del MVP

Flujo: `front/index.html` (Leaflet) ⇄ `back/server.py` (FastAPI) → `predict.py` (orquestación) → `geo.py` (lectura del raster) + `detector.py` (YOLO).

- **`almacen.py`** — cada ortomosaico subido vive en `UPLOAD_DIR/<id>/` (`imagen.tif` ya como COG, `meta.json`, `detecciones.json`). El id es un UUID hex generado por el servidor y es lo único que viaja en las URLs; nunca una ruta.
- **`server.py`** — todos los endpoints cuelgan de `/imagenes`:
  - Carga: `POST /imagenes?nombre=...` recibe el TIFF como **cuerpo crudo** (no multipart) y lo escribe a disco por partes; luego valida que sea un GeoTIFF con CRS y lo convierte a COG con el driver de GDAL si no lo es ya. La conversión es síncrona dentro de la petición. `GET /imagenes` lista las ya subidas.
  - Visualización: `/imagenes/{id}/tiles/{z}/{x}/{y}.png` y `/imagenes/{id}/metadata` usan `rio-tiler` para servir teselas XYZ directamente desde el COG; Leaflet las consume como `tileLayer`.
  - Análisis: `/imagenes/{id}/analizar-stream` (SSE) y `/imagenes/{id}/analizar` (POST, fallback que solo devuelve el último bloque) consumen el generador de `predict.py`.
- **`predict.py`** — `ejecutar_inspeccion_segmentada` es un **generador**: divide las celdas en ~10 segmentos y hace `yield` de un chunk por segmento (progreso + detecciones nuevas). El servidor serializa cada chunk como evento SSE. En el `finally` siempre escribe el JSON de detecciones (`ruta_json`; el servidor usa `detecciones.json` en la carpeta de la imagen) con lo acumulado, incluso si se interrumpe.
- **`geo.py`** — `GeoHandler` abre el TIFF con `rasterio` y lo recorre en una grilla de celdas de 640 px (tamaño de entrada de YOLO) leyendo por ventanas, sin cargar el raster completo. `obtener_lista_cuadrantes` permite limitar el análisis a uno de 4 cuadrantes (1=NO, 2=NE, 3=SO, 4=SE; otro valor = todo). `leer_tile_filtrado` devuelve `None` para celdas casi negras o sin textura, que así nunca llegan al modelo.
- **`detector.py`** — `FieldDetector` corre inferencia por lote sobre las celdas de un segmento y traduce las cajas a píxeles globales del ortomosaico sumando el offset de la celda.
- **`front/index.html`** — archivo único con JS inline; `API_BASE` es `/api` (nginx hace de proxy al backend) salvo que la página se abra como `file://`, donde usa `http://localhost:8000`. el umbral de confianza se elige con un control deslizante (10% por defecto). La subida usa `XMLHttpRequest` (no `fetch`) para poder mostrar el avance.

### Detalles que no son evidentes

- `gps_centro` de cada detección es el centro de la **celda de 640 px**, no el de la caja: todas las detecciones de una misma celda comparten coordenada y se superponen en el mapa. La posición precisa habría que derivarla de `box_global_px` con el transform del raster.
- `rasterio.transform.xy` devuelve coordenadas en el CRS del TIFF; `geo.py` las reproyecta a WGS84 cuando el raster no está en EPSG:4326 (p. ej. UTM).
- `fila`/`col` en las celdas son índices locales al cuadrante elegido, no a la grilla completa.
- CORS está abierto a `*` y no hay usuarios ni borrado de imágenes: cualquiera que acceda ve y analiza todas las subidas.
- Los `.py` y el `index.html` de `mvp/` usan fin de línea CRLF; los archivos de Docker y nginx, LF.
- En `front/nginx.conf`, `proxy_buffering off` es lo que permite que el SSE llegue bloque a bloque, y `proxy_request_buffering off` evita que nginx copie a disco cada subida antes de pasarla.
- `back/Dockerfile` instala `torch`/`torchvision` en su variante `+cpu`; sin eso la imagen suma varios GB de librerías CUDA.

## Modelo y dataset

YOLOv8n de detección (`yolov8n.pt`), entrenado en CPU (`epochs=50`, `imgsz=640`, `batch=2`). Las clases actuales en `entrenar ia/Dataset/dataset.yaml` son: `cana`, `arbol`, `camino`, `terreno sin plantar`, `plantacion creciendo`, `palmera` — todavía no hay una clase de maleza, y el dataset es de unas pocas imágenes.

Flujo de entrenamiento (del README): etiquetar con `labelme`, convertir a formato YOLO, actualizar `entrenar ia/Dataset/`, asegurar al menos una imagen etiquetada en `Dataset/images/val` (si falta, el entrenamiento falla con "No images found"; ver `entrenar ia/errores.txt`), ejecutar `train.py` y luego `predict.py` para verificar visualmente.
