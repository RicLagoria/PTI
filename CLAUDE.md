# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Proyecto Tecnológico Integrador (2026): aplicación web que analiza ortomosaicos GeoTIFF georreferenciados de campos de caña con un modelo YOLOv8 para detectar malezas y ubicarlas en un mapa. El código, los comentarios, los identificadores y los mensajes de commit están en español; mantener esa convención.

## Estado del repo: migración del MVP a servicios

El sistema se está partiendo en tres planos desplegables por separado (IA, Cliente, Entrenador), según **`docs/arquitectura.md`**, que hay que leer antes de agregar un servicio o mover código. La regla que ordena todo: **el servicio de IA no sabe de geografía** (recibe teselas, devuelve cajas en píxeles locales con un `id` opaco) y lo geoespacial queda en `cliente-api`.

**El código vigente está en `project/servicios/`** y ya corre completo con Docker (ver "Comandos de la arquitectura nueva"):

- `ia-inferencia` — FastAPI. `POST /detectar` recibe un lote de teselas y devuelve las cajas; carga `datos/modelos/activo/best.pt` en cada pedido, así que activar otra versión no requiere reiniciarlo.
- `ia-entrenamiento` — una imagen, dos comandos: la API (aportes de labelme, entrenamientos con progreso por SSE, registro de versiones) y el worker, que se puede escalar a varias réplicas. Con el registro vacío siembra `semilla/train-3` como modelo activo. Detalle en su README.
- `cliente-api` — FastAPI con login real (JWT contra PostgreSQL). Dueño de los ortomosaicos y de todo lo geoespacial; para analizar manda lotes de teselas a `ia-inferencia`.
- `cliente-web` — React + Leaflet: el front del MVP, con el login conectado a `cliente-api`.
- `entrenador-web` — React: subir aportes, entrenar y activar versiones. No tiene login ni backend propio; habla directo con la API de `ia-entrenamiento`.
- `base-datos` — esquema inicial de PostgreSQL + PostGIS (tabla `usuarios`). Las cuentas del equipo se cargan con `cliente-api/app/crear_usuarios.py`.

Compartido y despliegue:

- `contratos/` — OpenAPI de cada servicio y `clases.json`, la taxonomía canónica: hoy `maleza` y `falla`. El orden de esa lista es el índice de las etiquetas YOLO, así que solo se cambia por el final: las clases nuevas se agregan al final y solo se retira la última (así salieron `camino` y `lodazal`; ver `contratos/README.md`).
- `despliegue/` — un compose por plano (`compose.ia.yml`, `compose.cliente.yml`) y `compose.dev.yml` con todo en una máquina salvo el entrenamiento. Los volúmenes viven en `datos/`, en la raíz del repo e ignorado por git.
- `project/compartido/py-geo` — la lectura del raster de `geo.py` como paquete. `cliente-api` no usa este: instala su propia copia (`cliente-api/py-geo`), que ya difiere.
- `project/compartido/ts-api` — pensado para tipos generados desde los contratos; hoy tiene tipos escritos a mano, desactualizados, que ningún front importa.

**`project/mvp/` es el monolito anterior** y queda como referencia: un backend FastAPI que hace todo (teselas, lectura del raster e inferencia) y el front en React. Gran parte de este archivo todavía describe el MVP; la sección 9 de `docs/arquitectura.md` dice a dónde fue cada archivo. `project/entrenamiento` es un archivo vacío que quedó de la re-estructuración.

## Comandos

Backend en Python 3.9 (la imagen de Docker usa `python:3.9-slim`). No hay tests configurados; el único linter es ESLint en el front.

```bash
# Todo el MVP con Docker (front React + back detrás de nginx): http://localhost:8080
# Requiere los pesos en project/mvp/data/modelo/best.pt
cd project/mvp && mkdir -p data/modelo && cp ../servicios/ia-entrenamiento/semilla/train-3/weights/best.pt data/modelo/
cd project/mvp && docker compose up --build

# Backend sin Docker — debe ejecutarse desde project/mvp/back (rutas relativas al cwd)
pip install -r project/mvp/back/requirements.txt
cd project/mvp/back && MODEL_PATH=../../servicios/ia-entrenamiento/semilla/train-3/weights/best.pt uvicorn server:app --reload --port 8000

# Front sin Docker (Vite reenvía /api a http://localhost:8000)
cd project/mvp/front-react && npm install && npm run dev
cd project/mvp/front-react && npm run build   # tsc -b && vite build
cd project/mvp/front-react && npm run lint

# Pipeline de detección sin servidor (escribe detecciones_campo.json; espera "El Azul_COG.tif" en el cwd)
cd project/mvp/back && python predict.py
```

### Comandos de la arquitectura nueva (`project/servicios/`)

```bash
# Todo en una máquina para desarrollo: db:5432, ia-inferencia:8001, cliente-api:8000, cliente-web:8080
docker compose -f despliegue/compose.dev.yml up --build
# compose.dev.yml no trae el entrenamiento: se suma la parte de compose.ia.yml sin su ia-inferencia
# (chocaría en el 8001). Otro nombre de proyecto (-p) para que compose no los mezcle: los dos
# archivos están en despliegue/ y si no compartirían el nombre por defecto.
docker compose -p pti-ia -f despliegue/compose.ia.yml up --build ia-entrenamiento-api ia-entrenamiento-worker entrenador-web

# Despliegue por plano
docker compose -f despliegue/compose.cliente.yml up --build   # Plano Cliente: db, cliente-api, cliente-web
docker compose -f despliegue/compose.ia.yml up --build        # Plano IA: inferencia, entrenamiento (api + worker), entrenador-web:8003

# Cuentas del equipo para el login de cliente-web (con la base ya levantada; se puede repetir)
docker compose -f despliegue/compose.dev.yml run --rm cliente-api python crear_usuarios.py

# Sin Docker. Los servidores se corren desde app/: importan sus módulos sin paquete,
# igual que en la imagen (con "uvicorn app.server:app" falla el import)
cd project/servicios/ia-inferencia/app && MODEL_PATH=../../../../datos/modelos/activo/best.pt uvicorn server:app --port 8001 --reload

cd project/servicios/cliente-api && pip install -r requirements.txt ./py-geo
cd project/servicios/cliente-api/app && \
  DATABASE_URL=postgresql://agrovision:agrovision@localhost:5432/agrovision \
  IA_INFERENCIA_URL=http://localhost:8001 UPLOAD_DIR=../../../../datos/ortomosaicos \
  uvicorn server:app --port 8000 --reload

cd project/servicios/cliente-web && npm run dev   # Vite reenvía /api a localhost:8000
```

### Rutas y variables de entorno

Sin Docker, el backend resuelve todo contra el directorio de trabajo; `docker-compose.yml` apunta las variables al volumen `project/mvp/data/` (ignorado por git, montado en `/data`).

- `MODEL_PATH`: pesos de YOLO. El valor por defecto de `detector.py` (`runs/detect/train-2/weights/best.pt`) no existe en el repo, así que sin Docker hay que definirla siempre.
- `UPLOAD_DIR`: imágenes subidas. Por defecto `data/imagenes/`.
- `MAX_UPLOAD_MB`: tope de subida (8192 por defecto).
- `TAMANO_LOTE_MAX`: celdas por llamada a YOLO. 16 por defecto, 4 en el compose, que fue el óptimo medido en CPU (ver el comentario en `predict.py`).

No hay ortomosaicos versionados (`*.tif` está ignorado). En la raíz puede haber un recorte de prueba local, `crop_utm.tif`, en UTM.

## Arquitectura del MVP

Flujo: `front-react` (React + Leaflet) ⇄ nginx `/api` ⇄ `back/server.py` (FastAPI) → `predict.py` (orquestación) → `geo.py` (lectura del raster) + `detector.py` (YOLO).

### Backend (`project/mvp/back/`)

- **`almacen.py`** — cada ortomosaico subido vive en `UPLOAD_DIR/<id>/` (`imagen.tif` ya como COG, `meta.json`, `detecciones.json`). El id es un UUID hex generado por el servidor y es lo único que viaja en las URLs; nunca una ruta.
- **`server.py`** — todos los endpoints cuelgan de `/imagenes`:
  - Carga: `POST /imagenes?nombre=...` recibe el TIFF como **cuerpo crudo** (no multipart) y lo escribe a disco por partes; luego valida que sea un GeoTIFF con CRS y lo convierte a COG si no lo es ya. La conversión es síncrona dentro de la petición. `GET /imagenes` lista las ya subidas.
  - Visualización: `/imagenes/{id}/tiles/{z}/{x}/{y}.png` y `/imagenes/{id}/metadata` usan `rio-tiler` para servir teselas XYZ directamente desde el COG.
  - Análisis: `/imagenes/{id}/analizar-stream` (SSE) y `/imagenes/{id}/analizar` (POST, fallback que solo devuelve el último bloque) consumen el generador de `predict.py`. Ambos aceptan `cuadrante` y `conf`.
- **`predict.py`** — `ejecutar_inspeccion_segmentada` es un **generador**: parte las celdas en bloques de a lo sumo `TAMANO_LOTE_MAX` y hace `yield` de un chunk por bloque (progreso + detecciones nuevas). El servidor serializa cada chunk como evento SSE. En el `finally` siempre escribe el JSON de detecciones con lo acumulado, incluso si se interrumpe.
- **`geo.py`** — `GeoHandler` abre el TIFF con `rasterio` y lo recorre en una grilla de celdas de 640 px (tamaño de entrada de YOLO) leyendo por ventanas, sin cargar el raster completo. `obtener_lista_cuadrantes` permite limitar el análisis a uno de 4 cuadrantes (1=NO, 2=NE, 3=SO, 4=SE; otro valor = todo). `leer_tile_filtrado` devuelve `None` para celdas casi negras o sin textura, que así nunca llegan al modelo.
- **`detector.py`** — `FieldDetector` corre inferencia por lote sobre las celdas de un bloque y traduce las cajas a píxeles globales del ortomosaico sumando el offset de la celda.

### Frontend (`project/mvp/front-react/`)

React 19 + TypeScript + Vite, con HeroUI, Tailwind 4, `react-router-dom` y `react-leaflet`. Se construye con Node 20 y lo sirve nginx.

- Rutas en `src/App.tsx`: `/` (`Dashboard`: clima de Open-Meteo y resumen), `/campo` (`FieldView`: mapa, subida y análisis) y `/settings`. `Home` es el layout y muestra `LoginPage` si no hay sesión.
- `src/services/ImagenesService.ts` concentra las llamadas al backend. La subida usa `XMLHttpRequest` (no `fetch`) para poder mostrar el avance; el análisis en vivo usa `EventSource`.
- `ApiConfig.baseURL` es siempre `/api`: en Docker lo resuelve nginx y en `npm run dev` el proxy de `vite.config.ts`. Los dos quitan el prefijo antes de reenviar.
- El umbral de confianza se elige con un control deslizante (10% por defecto).

### Detalles que no son evidentes

- **El modelo se carga en cada análisis, no al arrancar.** `predict.py` instancia `FieldDetector` por corrida, así que reemplazar el archivo de `MODEL_PATH` surte efecto en el análisis siguiente sin reiniciar el backend.
- **Las clases no están escritas en ningún lado.** El backend las lee del modelo (`self.model.names`) y `FieldView` deriva el color de un hash del nombre y arma la leyenda desde las detecciones. Un modelo con clases nuevas funciona sin tocar código.
- **El login es decorativo.** `LoginPage` compara usuario y clave fijos en el navegador y guarda un indicador en `localStorage`. El backend no valida nada y CORS está abierto a `*`: quien llegue a la API ve y analiza todas las subidas. Tampoco hay borrado de imágenes.
- `gps_centro` de cada detección es el centro de la **celda de 640 px**, no el de la caja, así que es igual para todas las detecciones de una celda. `FieldView` no lo usa cuando puede: recalcula el centro de la caja desde `box_global_px` interpolando sobre los `bounds` de la metadata, lo que asume un raster orientado al norte y sin rotación.
- `rasterio.transform.xy` devuelve coordenadas en el CRS del TIFF; `geo.py` las reproyecta a WGS84 cuando el raster no está en EPSG:4326 (p. ej. UTM).
- `fila`/`col` en las celdas son índices locales al cuadrante elegido, no a la grilla completa.
- En `front-react/nginx.conf`, `proxy_buffering off` es lo que permite que el SSE llegue bloque a bloque, y `proxy_request_buffering off` evita que nginx copie a disco cada subida antes de pasarla.
- `back/Dockerfile` instala `torch`/`torchvision` en su variante `+cpu`; sin eso la imagen suma varios GB de librerías CUDA. El contenedor corre con el usuario del host, por eso define `YOLO_CONFIG_DIR` y `MPLCONFIGDIR` en `/tmp`.
- Los `.py` de `back/` usan fin de línea CRLF; el front en React, Docker, nginx y los documentos, LF.

## Modelo y dataset

YOLOv8n de detección. La corrida versionada es `project/servicios/ia-entrenamiento/semilla/train-3/` (pesos, `args.yaml`, `results.csv` y curvas), que `ia-entrenamiento` publica como primera versión del registro si arranca vacío, entrenada en CPU con `epochs=50`, `imgsz=640`, `batch=2`. Sus clases, en orden de índice: `maleza`, `falla`, `camino`, `lodazal`; las dos últimas ya no son canónicas, así que mientras esté activa los análisis pueden marcarlas.

El dataset no está en el repo: `args.yaml` apunta a una carpeta local de quien entrenó. `project/mvp/entrenamiento/train.py` es el script de entrenamiento del MVP y espera `Dataset/dataset.yaml` y `yolov8n.pt` en el directorio de trabajo.

Flujo actual, manual: etiquetar con `labelme`, convertir a formato YOLO, dejar al menos una imagen etiquetada en `images/val` (si falta, el entrenamiento falla con "No images found") y ejecutar `train.py`. El plano de IA de `docs/arquitectura.md` reemplaza este flujo por subida de aportes y entrenamiento desde la web.
