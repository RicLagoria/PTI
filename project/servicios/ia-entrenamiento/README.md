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

## Validación y evaluación de cada versión

Cada entrenamiento separa una parte de cada aporte para validar: 25% por
defecto, configurable entre 10% y 50% (`fraccion_validacion`). La cuenta por
aporte es `min(n - 1, max(1, floor(n * fraccion + 0.5)))`, la misma que muestra
entrenador-web antes de encolar.

Al terminar, el worker vuelve a validar `best.pt` (`worker/evaluacion.py`) y
guarda `evaluacion.json` junto a la versión. `GET /modelos/{v}/detalle` lo
devuelve con el historial por época de `results.csv`:

- métricas generales y por clase, con la cantidad de instancias de cada una;
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
uno corre más lento.

## Pesos de partida

`pesos_base` acepta `yolov8n.pt` o el nombre de una versión del registro, para
seguir entrenando un modelo anterior. Cualquier otro valor se rechaza: YOLO
abre los `.pt` con pickle, así que una ruta o URL libre permitiría ejecutar
código en el worker. `yolov8n.pt` se descarga de GitHub la primera vez que se
usa, así que el worker necesita salida a internet.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
