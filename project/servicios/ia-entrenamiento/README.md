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
   `cu128`. Se cambia con el build arg `VARIANTE_TORCH` (`cpu`), que son varios
   GB menos porque no se trae las librerías de NVIDIA.
3. **Acceso del contenedor al dispositivo**: `nvidia-container-toolkit` en el
   host y la reserva de GPU en el compose.

Las dos últimas las pone `compose.ia.yml`, que es el despliegue normal:

```bash
docker compose -f despliegue/compose.ia.yml up --build
```

El default es GPU a propósito. Desde una imagen con CUDA se entrena igual en
CPU (`dispositivo: cpu` es el valor por defecto de un trabajo), así que tenerla
no saca nada; al revés sí: con la imagen `+cpu` la opción GPU aparece
deshabilitada y hay que reconstruir para habilitarla. Lo que cuesta el default
son varios GB de imagen y que **en una máquina sin placa el `up` falla** con
"could not select device driver nvidia", para lo cual esta
`compose.ia.cpu.yml`:

```bash
docker compose -f despliegue/compose.ia.yml -f despliegue/compose.ia.cpu.yml up --build
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

## Hasta cuándo entrena: épocas y paciencia

`epocas` es el tope y `paciencia` corta antes (early stopping): si el modelo no
mejora en esa cantidad de épocas seguidas, la corrida termina ahí. `0` lo
desactiva. Lo implementa Ultralytics, y hay tres cosas que conviene saber:

- **Mira el fitness de validación, no la pérdida.** El fitness es el mAP50-95
  (en segmentación, el de la máscara más el de la caja). Es mejor criterio que la
  pérdida de YOLO, que mezcla cuatro términos (caja, clase, distribución de
  bordes, máscara) y puede bajar mientras el modelo detecta peor.
- **No cambia qué modelo se publica.** La versión sale siempre del `best.pt` de
  la época de mejor fitness, que YOLO guarda entrene 30 épocas más o no. Cortar
  solo ahorra tiempo de cómputo.
- **Cortar saltea el final de la receta.** En las últimas 10 épocas Ultralytics
  apaga el mosaico (`close_mosaic`) y las métricas suelen dar un salto; si el
  early stopping corta antes, ese salto no llega a pasar. Por eso el valor por
  defecto es 30 y no 10 como en los ejemplos típicos de Keras: el mAP sube a
  saltos y se amesetea, así que una paciencia corta corta de más. El default de
  Ultralytics, 100, es el otro extremo: con corridas de 150 épocas no corta
  nunca.

Las épocas que realmente corrió quedan en `metricas.epocas_entrenadas`, y
entrenador-web lo avisa en la tarjeta del trabajo: si no, "150 épocas" en el
pedido y 94 en la curva no cierran.

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
  modelo que ahí no hay nada, y una imagen ignorada no le enseña nada.

  Para pasar de lo segundo a lo primero está **`fondos_implicitos`**, un campo
  del formulario de subida (en la web, "las imágenes sin .json son fondo"): con
  él, cada imagen sin `.json` entra como ejemplo negativo, y el resultado dice
  cuántas fueron en `fondos_declarados`. Hace falta porque labelme no guarda una
  imagen en la que no se dibujó nada, así que las teselas limpias de un lote no
  dejan archivo.

  Viene **apagado** y se pide por aporte a propósito: declarar fondo una imagen
  que nadie revisó le enseña al modelo que la maleza que hay ahí no es maleza, y
  eso no se nota hasta que baja la recall. Si un lote está a medio etiquetar,
  conviene subir en un ZIP aparte solo las teselas ya revisadas.

  ```bash
  curl -X POST http://localhost:8002/datasets \
       -F archivo=@lote.zip -F nombre="Lote norte" -F fondos_implicitos=true
  ```

  Un aporte hecho **solo** de fondos es válido y sirve para las dos tareas: no
  tiene contornos, pero tampoco cajas, así que no hay nada que se pierda al
  entrenar segmentación con él (ver `tiene_segmentacion` en
  `nucleo/conversion_labelme.py`).

En cada entrenamiento, el 20% de las imágenes de cada aporte va a validación.

## Aportes de escala gruesa: `POST /datasets/{id}/ventanas`

El modelo mira el campo a través de una tesela de 640 px, que en un ortomosaico
de 3,3 cm/px son unos 21 m. Una mancha más grande no entra en la imagen y el
modelo nunca la ve entera, así que aprende a cortarla. En el dataset de El Azul
se mide: **una de cada cuatro manchas etiquetadas (24,9 %) toca el borde de su
tesela**, y el percentil 95 del lado está pegado a los 680 px, o sea que la
distribución está cortada por el encuadre y no por el campo.

El servicio arma la escala gruesa sin que haya que etiquetar nada de nuevo: pega
N×N teselas vecinas, reduce la ventana a 640 px y recompone las etiquetas con el
desplazamiento de cada tesela y el factor de reducción. Una ventana de 4×4 cubre
unos 89 m, así que la mancha que estaba cortada aparece entera.

**No hace falta volver a subir nada.** `datasets.guardar_dataset_zip` guarda cada
imagen con el nombre del `.json` de origen, así que la posición de la tesela
(`tile_x<col>_y<fila>`) sobrevive a la subida y con ella la vecindad: el aporte
ya guardado tiene todo lo que hace falta. En `entrenador-web` es el botón de
capas de cada aporte; por HTTP, `GET` dice qué escalas dan ventanas completas y
`POST` las genera:

```bash
curl http://localhost:8002/datasets/<id>/ventanas
curl -X POST http://localhost:8002/datasets/<id>/ventanas \
     -H 'Content-Type: application/json' -d '{"escalas":[2,3,4]}'
```

Cada escala queda registrada como un aporte nuevo, con su propio id y con
`derivado_de` y `escala` en el `meta.json`, y se mezcla en un entrenamiento igual
que cualquier otro.

Cuatro cosas que no son evidentes:

- **Une las manchas partidas por una costura interna.** Una mancha a caballo de
  dos teselas se etiquetó dos veces, media en cada una, y al pegarlas siguen
  siendo dos formas. Las que tocan una costura se rasterizan juntas por clase y
  se les vuelve a trazar el contorno, que es lo que las fusiona; las demás pasan
  tal cual, para no juntar dos manchas que el equipo dibujó aparte a propósito.
  Sin este paso la ventana grande tendría dos manchas pegadas donde hay una, que
  es el mismo error que se quiere corregir.
- **Las ventanas de una escala no se solapan**, y arrancan en múltiplos de la
  escala. Con paso de una tesela saldrían hasta N² veces más ventanas, pero casi
  iguales entre sí, y el split de validación es al azar dentro del aporte: dos
  ventanas corridas una tesela comparten casi todo el terreno, y si una cae en
  entrenamiento y la otra en validación las métricas no miden nada.
- **Una ventana se descarta si le falta una tesela.** Las teselas se agarran de
  un solo aporte, así que dos lotes vecinos subidos por separado no forman
  ventanas entre ellos; si interesa esa franja, conviene subirlos juntos.
- **Un contorno que son las cuatro esquinas de su caja se sigue contando en
  `contornos_de_caja`.** El dato se pierde al guardar el contorno como texto de
  YOLO, así que se vuelve a deducir de su forma: es el número que avisa que una
  parte del aporte no sirve para entrenar contornos.

**Ojo con comparar métricas entre versiones** cuando se entrena con estos
aportes: cubren el mismo terreno que el aporte del que salieron, a otra escala, y
el split de validación es por aporte. Una ventana de 4× puede caer en validación
mientras las teselas finas de ese mismo pedazo de campo están en entrenamiento, y
el mAP sale optimista. Para que vuelva a ser comparable haría falta partir
validación por geografía y no al azar, en `nucleo/ensamblado.py`.

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

## Comparar dos versiones: `comparar_escalas.py`

El mAP que publica un entrenamiento **no sirve para comparar dos versiones que
no se entrenaron con los mismos aportes**: cada una se midió contra su propio
split de validación. Y en cuanto se mezclan escalas deja de servir incluso para
una sola versión, porque un número solo no dice si mejoró en grueso o empeoró en
fino.

`comparar_escalas.py` corre la validación de cada versión sobre los mismos
aportes, agrupados por escala, y pone los números lado a lado. Se corre a mano,
dentro de la imagen (como `crear_usuarios.py` en cliente-api):

```bash
docker compose -p pti-ia -f despliegue/compose.ia.yml run --rm \
    ia-entrenamiento-api python comparar_escalas.py \
    --datasets <id-del-aporte-fino>,<id-del-aporte-4x>
```

Por defecto compara todas las versiones de segmentación del registro y usa la
GPU si está; `--versiones` y `--dispositivo` lo acotan.

Lo que hay que elegir bien son los aportes: tienen que ser **los mismos para
todas las versiones y, para que el número signifique algo, no haber entrenado a
ninguna**. El script avisa cuando una versión se entrenó con alguno de los que
se le pasaron (lo lee del `meta.json` de la versión), pero no se niega: comparar
sobre datos vistos sigue sirviendo para ordenar dos modelos entre sí, solo que
los valores absolutos salen optimistas.

Los aportes se agrupan por la escala que tienen en su `meta.json`; los que no la
tienen son de escala 1. Así, pasándole un aporte fino y su derivado de 4× se ve
en una tabla si una versión mejoró en grueso sin perder en fino, que es la única
forma de saber si conviene activarla para análisis en cascada.

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
