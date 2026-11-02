# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Proyecto Tecnológico Integrador (2026): aplicación web que analiza ortomosaicos GeoTIFF georreferenciados de campos de caña con un modelo YOLOv8 para detectar malezas, dibujar el contorno de cada mancha en un mapa y medir su superficie. El código, los comentarios, los identificadores y los mensajes de commit están en español; mantener esa convención.

## Estado del repo: migración del MVP a servicios

El sistema se está partiendo en tres planos desplegables por separado (IA, Cliente, Entrenador), según **`docs/arquitectura.md`**, que hay que leer antes de agregar un servicio o mover código. La regla que ordena todo: **el servicio de IA no sabe de geografía** (recibe teselas, devuelve cajas en píxeles locales con un `id` opaco) y lo geoespacial queda en `cliente-api`.

**El código vigente está en `project/servicios/`** y ya corre completo con Docker (ver "Comandos de la arquitectura nueva"):

- `ia-inferencia` — FastAPI. `POST /detectar` recibe un lote de teselas y devuelve las cajas y, con un modelo de segmentación, el contorno de cada mancha (`contorno_local`); carga `datos/modelos/activo/best.pt` en cada pedido, así que activar otra versión no requiere reiniciarlo. `GET /modelo` informa `tarea` (`segment` o `detect`), que sale del `.pt`.
- `ia-entrenamiento` — una imagen, dos comandos: la API (aportes de labelme, entrenamientos con progreso por SSE, registro de versiones; todo con autenticación salvo `GET /salud`) y el worker, que se puede escalar a varias réplicas. Con el registro vacío siembra `semilla/train-3` como modelo activo. Entrena contornos o cajas y en CPU o GPU (ver "Tareas y dispositivo"). Detalle en su README.
- `cliente-api` — FastAPI con login real (JWT contra PostgreSQL). Dueño de las cuentas: emite los tokens que usan los dos fronts, el de análisis y el del entrenador. Dueño también de los ortomosaicos y de todo lo geoespacial; para analizar manda lotes de teselas a `ia-inferencia` y georreferencia lo que vuelve, contornos incluidos (`georref.py`).
- `cliente-web` — React + Leaflet: el front del MVP, con el login conectado a `cliente-api`. Dibuja un `Polygon` por detección con contorno y cae al marcador cuando no lo hay.
- `entrenador-web` — React: subir aportes, entrenar (eligiendo contornos/cajas y CPU/GPU) y activar versiones. No tiene backend propio; habla directo con la API de `ia-entrenamiento`. **Tiene login, con las mismas cuentas que `cliente-web`**: su nginx reenvía `/auth` a `cliente-api`, que es quien las valida (ver "El login del entrenador").
- `base-datos` — esquema de PostgreSQL + PostGIS en `init/`, que Postgres corre **una sola vez** al crear el volumen: `01_esquema.sql` (tabla `usuarios`), `02_analisis.sql` (`ortomosaicos`, `analisis`, `detecciones`), `03_segmentacion.sql` (el contorno de cada detección), `04_escala.sql` (a qué escala corrió cada análisis) y `05_cascada.sql` (varias pasadas por análisis; reemplaza la columna de 04). Sobre una base que ya existe hay que aplicar los archivos nuevos a mano, son idempotentes; ver su README. Las cuentas del equipo se cargan con `cliente-api/app/crear_usuarios.py`.

Compartido y despliegue:

- `contratos/` — OpenAPI de cada servicio y `clases.json`, la taxonomía canónica: hoy `maleza` y `falla`. El orden de esa lista es el índice de las etiquetas YOLO, así que solo se cambia por el final: las clases nuevas se agregan al final y solo se retira la última (así salieron `camino` y `lodazal`; ver `contratos/README.md`).
- `despliegue/` — un compose por plano (`compose.ia.yml`, `compose.cliente.yml`), `compose.dev.yml` con todo en una máquina salvo el entrenamiento, y `compose.ia.cpu.yml`, un override de `compose.ia.yml` para una máquina sin placa NVIDIA. Instalarlo afuera de una máquina de desarrollo está en **`docs/instalacion-servidor.md`**, que incluye cómo llevarle los modelos ya entrenados al servidor que analiza. **`compose.ia.yml` construye con CUDA y reserva la GPU por defecto**, porque entrenar en CPU sigue disponible desde esa misma imagen y lo que no se puede deshacer en caliente es lo otro. Los volúmenes viven en `datos/`, en la raíz del repo e ignorado por git.
- `project/compartido/py-geo` — la lectura del raster de `geo.py` como paquete. `cliente-api` no usa este: instala su propia copia (`cliente-api/py-geo`), que ya difiere — entre otras cosas, `pixeles_globales_a_latlon` (reproyección de muchos puntos de una vez, para los vértices de un contorno) está solo en la de `cliente-api`.
- `project/compartido/ts-api` — pensado para tipos generados desde los contratos; hoy tiene tipos escritos a mano, desactualizados, que ningún front importa.

### El login del entrenador

`entrenador-web` reutiliza las cuentas de `cliente-web` (la tabla `usuarios`),
pero **el plano IA no las conoce**: valida contra `cliente-api` y en
`ia-entrenamiento` solo se verifica la firma del token (`api/auth.py`, con
`pyjwt` y nada más — sin `psycopg`, sin `bcrypt`, sin `DATABASE_URL`). Es la
misma regla que ordena lo geoespacial: el plano IA no se mete con lo que es del
plano Cliente.

Tres cosas que se desprenden de eso y conviene saber antes de tocarlo:

- **`JWT_SECRET` tiene que valer lo mismo en los dos planos.** Si no, el login
  del navegador sale bien y después todo pedido responde 401: es el primer lugar
  donde mirar cuando el entrenador te saca de la sesión apenas entrás.
- **Para entrar al entrenador hace falta que el plano Cliente esté arriba**, porque
  es el único que puede emitir un token. `entrenador-web` llega a él por su
  nginx, que reenvía `/auth` a `CLIENTE_API_URL` (por eso `nginx.conf` pasó a ser
  `nginx.conf.template`: la URL cambia según dónde esté el otro plano). En el
  navegador es el mismo origen, así que no hay CORS de por medio.
- **Dos endpoints llevan el token en la URL y no en el header**, porque no pueden
  mandar headers: el SSE del progreso (`EventSource`) y los gráficos de cada
  modelo (`<img src>`). Es lo mismo que ya hacía `cliente-api` con las teselas.

Entra cualquier usuario de la tabla: la columna `rol` se muestra y no restringe
nada, igual que en `cliente-web`.

### Detalles de la segmentación que no son evidentes

- **El contorno viaja en dos órdenes distintos.** `georref.traducir_deteccion` lo entrega como `[[lat, lon], ...]` porque así lo consume Leaflet, y `datos.insertar_detecciones` lo da vuelta a lon/lat para PostGIS. Al leerlo de la base se vuelve a dar vuelta, así el front no distingue un análisis en vivo de uno guardado.
- **La columna `detecciones.contorno` es `MULTIPOLYGON`, no `POLYGON`.** El contorno de una máscara puede salir con el borde cruzado, y `ST_MakeValid` arregla ese anillo partiéndolo en varios. Al leer se devuelve la pieza de mayor área (las otras son esquirlas de unos píxeles), pero la superficie se mide sobre todas.
- **La superficie se calcula en dos lugares a propósito.** Un análisis en vivo manda las detecciones al navegador antes de leerlas de vuelta, así que `georref.area_m2` la calcula ahí con un plano tangente al contorno (se aparta menos del 0,1 % a escala de una mancha); al leer un análisis guardado la calcula PostGIS con `ST_Area(contorno::geography)`.
- **El contorno se simplifica en `ia-inferencia`, no en el cliente.** El borde crudo de una máscara tiene cientos de vértices casi colineales, y ese contorno viaja hasta el navegador y se guarda en la base.
- **El tamaño de la celda ya no es el de entrada del modelo, y un análisis
  puede recorrer el campo varias veces.** `escalas` (una lista, "1" por
  defecto) son las pasadas en orden: en una de escala N la celda son
  `imgsz * N` píxeles del raster reducidos a `imgsz`, o sea el mismo encuadre
  con más campo. Con `4,1` la cámara primero se aleja y después se acerca.
  Queda guardado en `analisis.escalas`, y cada detección anota de qué pasada
  salió en `detecciones.escala`. Alejarse sale **más barato**: los overviews del COG hacen
  la reducción (leer una celda de 2560 px cuesta 16 ms contra 11 ms una de 640)
  y hay 16 veces menos celdas. Lo que sí hay que saber es que `georref` deshace
  la reducción con el `factor_x`/`factor_y` de cada celda y no con la escala,
  porque en una celda del borde del raster no son lo mismo.
- **Las dos pasadas de una cascada coinciden en menos de la mitad del terreno.**
  Medido sobre un cuadrante con `4,1`: la gruesa cubre 32 892 m2, la fina
  32 660, comparten 14 852 y cada una aporta unos 18 000 que la otra no vio. Con
  el modelo entrenado solo con teselas finas, la pasada gruesa está fuera de su
  distribución y marca manchas de casi la celda entera, así que **ese aporte no
  se puede dar por bueno todavía**: la cascada sirve recién con un modelo
  entrenado con los aportes de escala gruesa. Por eso `escalas` es "1" por
  defecto y `datos.superficie_real` devuelve `por_escala`, para que la
  diferencia no quede escondida en un total.
- **Al terminar cada pasada se fusionan las detecciones partidas por el borde
  de una celda** (`datos.fusionar_detecciones_vecinas`), y recién al terminar
  porque las dos mitades pueden haber salido en bloques distintos del streaming.
  Se une **solo entre celdas distintas y vecinas de la misma pasada**: medido sobre un análisis
  real, de los pares de la misma clase que se tocan, 284 estaban dentro de una
  misma celda (manchas que el modelo separó a propósito) y 54 cruzaban el borde.
  El navegador ya recibió las piezas sueltas por SSE, así que el chunk final
  avisa con `fusion` y hay que recargar para ver lo guardado.
- **Después de fusionar se suprimen las detecciones anidadas.** YOLO hace NMS
  sobre las cajas y no sobre las máscaras, así que la misma mancha puede quedar
  detectada dos veces, una adentro de la otra: medido, el 74 % de los pares que
  se cruzan tienen una con el 90 % o más de su superficie dentro de la otra.
  `datos.suprimir_detecciones_anidadas` borra la chica y deja la grande, que la
  contiene, y solo compara dentro de una misma pasada (entre escalas distintas
  que una contenga a otra es lo esperado, no un duplicado) (no la más confiable: en esos pares la grande es la más confiable
  apenas el 56 % de las veces).
- **Sumar `area_m2` por detección NO da la superficie afectada.** Aun después de
  suprimir quedan pares que se pisan parcialmente, y ese suelo se cuenta dos
  veces: la suma da ~6 % de más (18 % en un análisis del pipeline viejo). La
  respuesta correcta es `datos.superficie_real`, que la calcula con
  `ST_Area(ST_Union(contorno))` y es lo que usa el informe en PDF. Su total no
  es la suma de las clases, porque dos clases también pueden pisarse.
- **El dashboard sigue midiendo cobertura por celdas de 640 px,** no por superficie de los contornos (`datos.estadisticas_dashboard`): ahora que hay áreas reales, eso se puede mejorar.

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
# El entrenador necesita el cliente-api de arriba para el login: queda en otra red de compose,
# así que su nginx lo busca en el host (CLIENTE_API_URL, ya configurado por defecto).
docker compose -p pti-ia -f despliegue/compose.ia.yml up --build ia-entrenamiento-api ia-entrenamiento-worker entrenador-web

# Despliegue por plano
docker compose -f despliegue/compose.cliente.yml up --build   # Plano Cliente: db, cliente-api, cliente-web
docker compose -f despliegue/compose.ia.yml up --build        # Plano IA: inferencia, entrenamiento (api + worker), entrenador-web:8003

# Plano IA en una máquina sin placa NVIDIA. Es un override, van los dos -f: saca la
# reserva de GPU (sin esto el "up" falla antes de arrancar) y construye con torch +cpu,
# varios GB menos. Entrenar en CPU anda igual, que es el default de un trabajo.
docker compose -f despliegue/compose.ia.yml -f despliegue/compose.ia.cpu.yml up --build

# Cuentas del equipo para el login de cliente-web (con la base ya levantada; se puede repetir)
docker compose -f despliegue/compose.dev.yml run --rm cliente-api python crear_usuarios.py

# Migración de una base que ya existe (init/ solo corre al crear el volumen). Idempotente.
docker compose -f despliegue/compose.dev.yml exec -T db psql -U agrovision -d agrovision < project/servicios/base-datos/init/03_segmentacion.sql
docker compose -f despliegue/compose.dev.yml exec -T db psql -U agrovision -d agrovision < project/servicios/base-datos/init/04_escala.sql
docker compose -f despliegue/compose.dev.yml exec -T db psql -U agrovision -d agrovision < project/servicios/base-datos/init/05_cascada.sql

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

### Tareas y dispositivo

Un entrenamiento tiene dos ejes y **se piden distinto a propósito**:

- **Qué entrena no es un parámetro: viene con `pesos_base`.** `yolov8n-seg.pt` entrena contornos (`tarea: segment`), `yolov8n.pt` cajas (`detect`), y una versión del registro sigue con su misma tarea, anotada en su `meta.json`. El `.pt` trae la cabeza entrenada para una cosa o la otra y no se puede seguir entrenando una con las etiquetas del otro formato; si la tarea fuera un campo aparte podría contradecir a los pesos. La lista de pesos permitidos es un allowlist (`registro.TAREA_DE_PESOS_OFICIALES`): YOLO abre los `.pt` con pickle.
- **Dónde entrena sí es un parámetro: `dispositivo`,** `cpu` (por defecto) o `gpu`. Para GPU hacen falta tres cosas (la placa, un torch con CUDA, el acceso del contenedor al dispositivo) y `nucleo/dispositivos.py` las distingue para poder decir cuál falta; `GET /dispositivos` lo expone y `entrenador-web` habilita o no la opción. Si se pide GPU y el worker no la tiene, el trabajo queda **fallido en el momento**, antes de copiar el dataset: entrenar en CPU sin avisar serían horas de cómputo que nadie pidió. El dispositivo también fija el lote (`LOTE_CPU`=2, `LOTE_GPU`=16).

- **Hasta cuándo entrena son dos parámetros:** `epocas` es el tope y
  `paciencia` corta antes si el fitness de validación (mAP, no la pérdida) no
  mejora en esa cantidad de épocas seguidas; 0 la desactiva, 30 por defecto. No
  cambia qué modelo se publica, porque la versión sale del `best.pt` de la mejor
  época: solo ahorra cómputo. Cortar antes también saltea las últimas 10 épocas,
  en las que Ultralytics apaga el mosaico y las métricas dan un salto.

**El encuadre también es un parámetro del dataset, no solo del análisis.** Una
tesela de 640 px son unos 21 m a 3,3 cm/px, así que una mancha más grande no
entra y el modelo aprende a cortarla: el 24,9 % de las manchas etiquetadas toca
el borde de su tesela. `POST /datasets/{id}/ventanas` (`nucleo/ventanas.py`)
deriva aportes de escala gruesa pegando N×N teselas vecinas del aporte **ya
subido** y reduciéndolas a 640, sin reetiquetar ni volver a subir nada: las
teselas se guardan con el nombre de su `.json`, así que `tile_x<col>_y<fila>`
sobrevive y con él la vecindad. Une las manchas partidas por las costuras. Ver
el README del servicio, incluida la advertencia sobre comparar métricas.

De cada aporte se guardan los **dos** formatos de etiqueta al subirlo: `etiquetas/` las cajas y `contornos/` los polígonos (`conversion_labelme.py`). Así el mismo aporte sirve para las dos tareas y recién al encolar se elige la carpeta (`ensamblado.CARPETA_ETIQUETAS_POR_TAREA`). Los aportes subidos antes de que se guardaran los contornos solo sirven para `detect`; la API y el ensamblado los rechazan con un mensaje que explica que hay que volver a subir el ZIP, porque los polígonos siguen estando en sus JSON de labelme.

### La semilla

`project/servicios/ia-entrenamiento/semilla/train-3/` (pesos, `args.yaml`, `results.csv` y curvas) es un YOLOv8n **de detección**, entrenado en CPU con `epochs=50`, `imgsz=640`, `batch=2`; `ia-entrenamiento` la publica como primera versión del registro si arranca vacío, para que haya algo con qué analizar hasta que se entrene una versión `segment`. Mientras esté activa, el mapa marca puntos y no manchas. Sus clases, en orden de índice: `maleza`, `falla`, `camino`, `lodazal`; las dos últimas ya no son canónicas, así que mientras esté activa los análisis pueden marcarlas.

El dataset no está en el repo: `args.yaml` apunta a una carpeta local de quien entrenó. `project/mvp/entrenamiento/train.py` es el script de entrenamiento del MVP y espera `Dataset/dataset.yaml` y `yolov8n.pt` en el directorio de trabajo.

Flujo del MVP, manual: etiquetar con `labelme`, convertir a formato YOLO, dejar al menos una imagen etiquetada en `images/val` (si falta, el entrenamiento falla con "No images found") y ejecutar `train.py`. En `project/servicios/` eso ya está reemplazado por la subida de aportes y el entrenamiento desde `entrenador-web`.
