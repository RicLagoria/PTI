# ia-entrenamiento

Plano IA. Recibe aportes etiquetados, entrena y mantiene el registro de
versiones del modelo. Una sola imagen de Docker con dos comandos: la API y el
worker.

- `nucleo/` — código compartido por los dos: conversión de labelme a YOLO,
  remapeo de clases, cola de trabajos en disco y registro de modelos.
- `api/` — servidor FastAPI: datasets, entrenamientos (SSE) y modelos.
- `worker/` — reclama el trabajo pendiente más viejo de la cola y lo entrena
  (sale de `mvp/entrenador yolov8/train.py`). Se puede escalar a varias
  réplicas; ver "Varios workers".

Un entrenamiento publica una versión nueva pero nunca la activa: activar es un
paso explícito.

## Qué entrena: contornos o cajas

Dos tareas de YOLO, y de cada una sale un análisis distinto en el mapa:

| Tarea | Pesos de partida | Qué devuelve el análisis |
|---|---|---|
| `segment` | `yolov8n-seg.pt` | El contorno de cada mancha y su superficie: el mapa dibuja polígonos |
| `detect` | `yolov8n.pt` | La caja que la encierra: el mapa marca un punto |

**La tarea no es un parámetro del pedido: viene con `pesos_base`.** El `.pt` trae
la cabeza entrenada para cajas o para máscaras, y no se puede seguir entrenando
una con las etiquetas del otro formato; si la tarea fuera un campo aparte podría
contradecir a los pesos y el error saldría recién desde dentro de Ultralytics.
Una versión del registro sigue entrenando con su misma tarea, que quedó anotada
en su `meta.json` (las publicadas antes de que existiera segmentación son
`detect`, igual que la semilla).

De cada aporte se guardan **los dos formatos de etiqueta** al subirlo
(`etiquetas/` las cajas, `contornos/` los polígonos), así que el mismo aporte
sirve para las dos tareas y recién al encolar el trabajo se decide cuál se usa.
Los aportes subidos antes de que se guardaran los contornos solo sirven para
`detect`; para usarlos con `segment` hay que volver a subir el ZIP, porque los
polígonos siguen estando en sus JSON de labelme.

## Dónde entrena: CPU o GPU

`dispositivo` es `cpu` (por defecto) o `gpu`. En CPU un entrenamiento de unos
cientos de imágenes lleva horas; en una GPU NVIDIA decente, minutos.

Para que la GPU funcione hacen falta tres cosas, y las tres fallan distinto:

1. **La placa y su driver** en la máquina: `nvidia-smi` la tiene que ver.
2. **Un torch con CUDA.** La imagen se construye por defecto con las ruedas
   `+cpu`, porque las de CUDA se traen las librerías de NVIDIA y le suman varios
   GB. Se cambia con el build arg `VARIANTE_TORCH` (`cu128`).
3. **Acceso del contenedor al dispositivo**: `nvidia-container-toolkit` en el
   host y la reserva de GPU en el compose.

La reserva la pone el override de compose, y con él se construye la imagen CUDA:

```bash
docker compose -f despliegue/compose.ia.yml -f despliegue/compose.ia.gpu.yml up --build
```

El toolkit se instala una vez por máquina, desde el repo de NVIDIA (que es
independiente de la distribución). Desde la versión 1.20 el paquete deja solo
los specs CDI en `/etc/cdi/nvidia.yaml` y registra el runtime `nvidia` en
Docker, con una unidad de systemd (`nvidia-cdi-refresh.path`) que los regenera
cuando cambia el driver; en versiones anteriores hay que hacer esos dos pasos a
mano con `nvidia-ctk cdi generate` y `nvidia-ctk runtime configure`. Para
comprobar que quedó andando, antes de meter el proyecto en el medio:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

Si eso no lista la placa, el problema es del host y no de estos archivos.

`GET /dispositivos` dice si hay GPU y, si no, cuál de las tres falta;
entrenador-web lo usa para habilitar la opción y mostrar el motivo. Describe lo
que ve la API, no el worker (son contenedores distintos, aunque en los dos
compose corran en la misma máquina y desde la misma imagen), así que la palabra
final la tiene el worker: si se pide GPU y no la tiene, el trabajo queda
**fallido en el momento** con ese motivo, antes de copiar el dataset. Entrenar
en CPU "por las dudas" serían horas de cómputo que nadie pidió.

El dispositivo también fija el tamaño de lote: `LOTE_CPU` (2, el valor con el
que se entrenó train-3, donde manda la RAM) o `LOTE_GPU` (16, donde manda la
VRAM; bajarlo si el entrenamiento se cae con "CUDA out of memory").

Un lote más grande también necesita más **memoria compartida**: el dataloader de
YOLO le pasa las imágenes a sus procesos auxiliares por `/dev/shm`, y los 64 MB
que Docker le da por defecto a un contenedor no alcanzan para un lote de GPU. Un
lote de 2 entraba justo, así que el problema aparece recién al entrenar en GPU, y
no se parece a falta de memoria: el entrenamiento falla antes de la primera época
con `DataLoader worker (pid N) is killed by signal: Bus error`. Por eso
`compose.ia.yml` le da `shm_size: 2gb` al worker; si se sube `LOTE_GPU` bastante,
hay que subirlo también.

## Cómo subir un aporte

Un ZIP con las imágenes y los `.json` que guarda labelme, en cualquier
estructura de carpetas. Al subirlo se convierte a YOLO y se rechaza **entero**
si algo no sirve, con el detalle de qué corregir:

- **Etiquetas:** se comparan por nombre contra `contratos/clases.json`,
  ignorando mayúsculas y espacios de más. Una etiqueta que no está en la lista
  rechaza el aporte; los índices que haya asignado cada labelme no se usan.
- **Formas:** de rectángulos, polígonos y círculos se saca la caja que los
  encierra **y** el contorno, que es lo que entrena segmentación: los vértices
  tal como se dibujaron en un polígono, 16 vértices en un círculo y las cuatro
  esquinas en un rectángulo. Esos últimos se cuentan aparte
  (`contornos_de_caja`): entrenar segmentación con ellos le enseña rectángulos
  al modelo. Puntos y líneas se ignoran y se informan.
- **Imágenes:** se busca la de cada `.json` por su `imagePath`, o por el mismo
  nombre del `.json`, o embebida en `imageData`. Si mide distinto de lo que
  dice el `.json` se rechaza, porque las etiquetas quedarían corridas.
- **Fondos:** un `.json` sin formas entra como ejemplo negativo. Una imagen sin
  `.json` se ignora (puede ser un descuido) y se informa en el resultado como
  `imagenes_sin_anotar`. La diferencia importa: un fondo declarado le enseña al
  modelo que ahí no hay nada, y una imagen ignorada no le enseña nada. Para
  pasar de lo segundo a lo primero está `herramientas/marcar_fondos.py`, que le
  escribe el `.json` vacío a cada imagen que se le indique (labelme no guarda
  una imagen en la que no se dibujó nada), sin tocar las que ya tienen uno:

  ```bash
  cd <carpeta del lote>
  python <repo>/project/servicios/ia-entrenamiento/herramientas/marcar_fondos.py *.jpg
  ```

  Un aporte hecho **solo** de fondos es válido y sirve para las dos tareas: no
  tiene contornos, pero tampoco cajas, así que no hay nada que se pierda al
  entrenar segmentación con él (ver `tiene_segmentacion` en
  `nucleo/conversion_labelme.py`).

En cada entrenamiento, el 20% de las imágenes de cada aporte va a validación.

## Validación y evaluación de cada versión

Cada entrenamiento separa una parte de cada aporte para validar: 25% por
defecto, configurable entre 10% y 50% (`fraccion_validacion`). La cuenta por
aporte es `min(n - 1, max(1, floor(n * fraccion + 0.5)))`, la misma que muestra
entrenador-web antes de encolar.

Al terminar, el worker vuelve a validar `best.pt` (`worker/evaluacion.py`) y
guarda `evaluacion.json` junto a la versión. `GET /modelos/{v}/detalle` lo
devuelve con el historial por época de `results.csv`:

- métricas generales y por clase, con la cantidad de instancias de cada una;
- en segmentación, `metricas_mascara` además de las de caja: las de caja dicen
  si encontró la mancha, las de máscara si le dibujó bien el borde. Un mAP de
  caja alto con uno de máscara bajo es el síntoma de contornos flojos;
- el umbral de confianza que maximiza el F1 (no se recomienda si el F1 es casi
  cero);
- la matriz de confusión con ese umbral, en filas = clase real, con el fondo
  al final;
- las curvas de precisión, recall y F1 según la confianza.

Hay que leerla con cuidado: son las mismas imágenes con las que se eligió la
mejor época, así que la estimación es algo optimista y solo se compara de igual
a igual entre versiones entrenadas con los mismos aportes. Si la evaluación
falla, el modelo igual se publica y el error queda en `error_evaluacion` del
`meta.json`.

## Semilla

`semilla/train-3/` es la corrida con la que se entrenó el modelo del MVP. Si
la API arranca con el registro vacío, la publica como primera versión y la
activa, para que `ia-inferencia` tenga modelo desde la primera instalación.
`clases.json` declara sus clases: si dejan de coincidir con el principio de la
lista canónica, no se siembra.

Es un modelo `detect`: marca puntos, no contornos. Está para que una instalación
nueva tenga algo con qué analizar hasta que se entrene una versión `segment` con
los contornos de los aportes.

## Progreso y cancelación

Mientras entrena, el worker publica en el trabajo un `progreso`:
- la fase: `preparando`, `entrenando` o `evaluando`;
- la fracción hecha, que avanza por lote dentro de cada época;
- el tiempo transcurrido;
- los segundos restantes, estimados con el ritmo medido hasta ahí, que ya
  incluye la validación de cada época.

Escribe como mucho cada 2 segundos, y cada escritura es también su `latido`.
También da latido, sin mover la barra, mientras copia el dataset, en cada lote
de la validación de cada época y durante la evaluación final. La evaluación
final no entra en la estimación.

`POST /entrenamientos/{id}/cancelar` deja una marca `trabajos/<id>.cancelar`.
El worker la revisa en cada lote y al pasar de fase: corta, no publica ninguna
versión y borra la corrida. Un trabajo pendiente se cancela en el momento,
reservándolo con el mismo `.lock` que usan los workers. Si un trabajo en
ejecución no da latidos hace más de `LATIDO_MAXIMO_S` (su worker murió y no hay
otro que lo retome), la cancelación se aplica sin esperarlo.

## Varios workers

`docker compose -f despliegue/compose.ia.yml up -d --scale ia-entrenamiento-worker=3`
levanta tres réplicas. Cada una reclama un trabajo creando `trabajos/<id>.lock`
con `O_EXCL`, así dos réplicas nunca entrenan el mismo; el trabajo guarda en
`worker` cuál lo tomó. Cada intento trabaja en su propia carpeta
(`trabajos/<id>/intento-N/`) y cada trabajo publica una versión con nombre
propio, así que corren en paralelo sin pisarse.

Los archivos de cada trabajo en `trabajos/` son su estado: `<id>.json`, las
reservas (`<id>.lock`, `<id>.lock2`…), `<id>.cancelar` y `<id>.fin`, que marca
que terminó. Los workers eligen candidatos por los nombres de archivo y solo
abren los JSON de los que no terminaron, así el historial no los frena.

**Si una réplica muere** a mitad de un entrenamiento (reinicio, falta de
memoria), su trabajo deja de dar latido. Pasado `LATIDO_MAXIMO_S` (600 s por
defecto), otra réplica lo retoma desde cero en un intento nuevo, con una
reserva exclusiva por intento para que no lo tomen dos. Después de
`MAX_INTENTOS` (2 por defecto) queda fallido, para no reintentar para siempre
un trabajo que tumba al worker. Si la réplica en realidad seguía viva (por
ejemplo, estuvo pausada), en su siguiente escritura ve que el trabajo ya no es
suyo y lo abandona sin escribir nada.

En una máquina sin GPU, cada entrenamiento ya usa todos los núcleos: varias
réplicas sirven para que un entrenamiento largo no frene la cola, pero cada
uno corre más lento. Con una sola GPU pasa lo mismo y peor: dos réplicas
entrenando a la vez se pelean la VRAM y pueden caerse las dos por falta de
memoria, así que conviene una sola réplica con acceso a la placa.

## Pesos de partida

`pesos_base` acepta `yolov8n-seg.pt`, `yolov8n.pt` o el nombre de una versión
del registro, para seguir entrenando un modelo anterior. Cualquier otro valor se
rechaza: YOLO abre los `.pt` con pickle, así que una ruta o URL libre permitiría
ejecutar código en el worker. Los dos oficiales se descargan de GitHub la
primera vez que se usan, así que el worker necesita salida a internet.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
