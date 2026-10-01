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
# Dependencias del MVP (ojo: el nombre del archivo tiene un espacio)
pip install -r "mvp/requerimientos .txt"

# Backend (FastAPI) — debe ejecutarse desde mvp/back, ver "Rutas relativas"
cd mvp/back && uvicorn server:app --reload --port 8000

# Pipeline de detección sin servidor (escribe detecciones_campo.json)
cd mvp/back && python predict.py

# Frontend: HTML estático sin build; abrir mvp/front/index.html en el navegador

# Entrenamiento (desde la carpeta que contiene Dataset/ y yolov8n.pt)
cd "entrenar ia" && python train.py
```

El `requerimientos.txt` de la raíz corresponde al entorno de entrenamiento/etiquetado (labelme, labelme2yolo, etc.), no al servidor web.

### Rutas relativas (requisito para ejecutar)

El backend resuelve todo contra el directorio de trabajo y ninguno de estos archivos está en `mvp/back/`:

- Pesos: `runs/detect/train-2/weights/best.pt` (hardcodeado en `detector.py` y `predict.py`). Los pesos reales están en `entrenar ia/runs/detect/train-2/weights/`.
- Ortomosaico: `El Azul_COG.tif` (`RUTA_COG_DEFAULT` en `server.py`). No está en el repo; debe ser un Cloud Optimized GeoTIFF.

Hay que copiarlos/enlazarlos dentro de `mvp/back/` o pasar `tif_path` como query param.

## Arquitectura del MVP

Flujo: `front/index.html` (Leaflet) ⇄ `back/server.py` (FastAPI) → `predict.py` (orquestación) → `geo.py` (lectura del raster) + `detector.py` (YOLO).

- **`server.py`** expone dos funciones independientes sobre el mismo TIFF:
  - Visualización: `/tiles/{z}/{x}/{y}.png` y `/metadata` usan `rio-tiler` para servir teselas XYZ directamente desde el COG; Leaflet las consume como `tileLayer`.
  - Análisis: `/analizar-stream` (SSE) y `/analizar` (POST, fallback que solo devuelve el último bloque) consumen el generador de `predict.py`.
- **`predict.py`** — `ejecutar_inspeccion_segmentada` es un **generador**: divide las celdas en ~10 segmentos y hace `yield` de un chunk por segmento (progreso + detecciones nuevas). El servidor serializa cada chunk como evento SSE. En el `finally` siempre escribe `detecciones_campo.json` con lo acumulado, incluso si se interrumpe.
- **`geo.py`** — `GeoHandler` abre el TIFF con `rasterio` y lo recorre en una grilla de celdas de 640 px (tamaño de entrada de YOLO) leyendo por ventanas, sin cargar el raster completo. `obtener_lista_cuadrantes` permite limitar el análisis a uno de 4 cuadrantes (1=NO, 2=NE, 3=SO, 4=SE; otro valor = todo). `leer_tile_filtrado` devuelve `None` para celdas casi negras o sin textura, que así nunca llegan al modelo.
- **`detector.py`** — `FieldDetector` corre inferencia por lote sobre las celdas de un segmento y traduce las cajas a píxeles globales del ortomosaico sumando el offset de la celda.
- **`front/index.html`** — archivo único con JS inline; `API_BASE` apunta a `http://localhost:8000` y el cuadrante (3) y `conf` (0.10) están fijos en la URL del `EventSource`.

### Detalles que no son evidentes

- `gps_centro` de cada detección es el centro de la **celda de 640 px**, no el de la caja: todas las detecciones de una misma celda comparten coordenada y se superponen en el mapa. La posición precisa habría que derivarla de `box_global_px` con el transform del raster.
- `geo.py` nombra `lon, lat` a lo que devuelve `rasterio.transform.xy`, que está en el CRS del TIFF. Solo son grados válidos para Leaflet si el raster está en EPSG:4326; con un CRS proyectado (UTM) hay que reproyectar.
- `fila`/`col` en las celdas son índices locales al cuadrante elegido, no a la grilla completa.
- CORS está abierto a `*` y `tif_path` es un query param que se abre sin validar: aceptable para el MVP local, no para exponerlo.

## Modelo y dataset

YOLOv8n de detección (`yolov8n.pt`), entrenado en CPU (`epochs=50`, `imgsz=640`, `batch=2`). Las clases actuales en `entrenar ia/Dataset/dataset.yaml` son: `cana`, `arbol`, `camino`, `terreno sin plantar`, `plantacion creciendo`, `palmera` — todavía no hay una clase de maleza, y el dataset es de unas pocas imágenes.

Flujo de entrenamiento (del README): etiquetar con `labelme`, convertir a formato YOLO, actualizar `entrenar ia/Dataset/`, asegurar al menos una imagen etiquetada en `Dataset/images/val` (si falta, el entrenamiento falla con "No images found"; ver `entrenar ia/errores.txt`), ejecutar `train.py` y luego `predict.py` para verificar visualmente.
