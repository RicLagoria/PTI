# Instalación en un servidor

Guía para poner AgroVision a andar fuera de una máquina de desarrollo, y para
llevar los modelos ya entrenados al servidor que va a analizar.

Para el diseño de por qué el sistema está partido así, ver
[arquitectura.md](arquitectura.md). Acá solo están los comandos.

---

## 1. Qué se instala y dónde

El sistema son **dos planos** que se despliegan por separado. Pueden ir en la
misma máquina o en dos distintas.

| Plano | Servicios | Puertos | ¿Necesita GPU? |
|---|---|---|---|
| **Cliente** | `db`, `cliente-api`, `cliente-web` | 8000, 8080 | No, nunca |
| **IA** | `ia-inferencia`, `ia-entrenamiento` (API + worker), `entrenador-web` | 8001, 8002, 8003 | Solo para **entrenar** |

Lo importante para elegir: **analizar nunca necesita GPU**. `ia-inferencia` se
construye con torch `+cpu` desde siempre. La placa hace falta únicamente si en
esa máquina se van a *entrenar* modelos nuevos.

De ahí salen las dos recetas de abajo: el servidor con GPU es el que entrena, y
el servidor sin GPU es el que analiza con los modelos que le copiás.

---

## 2. Requisitos

En las dos máquinas:

- Docker Engine y el plugin Compose **v2.24 o posterior** (`docker compose
  version`). La 2.24 hace falta por la etiqueta `!override` que usa
  `compose.ia.cpu.yml`.
- El repositorio clonado.
- La carpeta `datos/` en la raíz del repo, que es donde viven todos los
  volúmenes. Está ignorada por git y se crea sola al levantar.

Solo en el servidor que va a entrenar:

- Placa NVIDIA, driver y **NVIDIA Container Toolkit**. Se comprueba así:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

Si ese comando no muestra la placa, el `up` del plano IA con GPU va a fallar
con `could not select device driver "nvidia" with capabilities: [[gpu]]`.

---

## 3. Antes de levantar nada: el archivo `.env`

Compose lee `despliegue/.env` aunque los comandos se corran desde la raíz del
repo. Ahí van las variables que **no** pueden quedarse con el valor por defecto.

Creá `despliegue/.env` en **cada** máquina:

```bash
# El secreto con el que se firman los tokens de sesión.
# TIENE QUE SER EL MISMO EN LOS DOS PLANOS. Generalo una vez y copialo.
JWT_SECRET=pegar-acá-el-valor-generado

# Contraseña de PostgreSQL (solo plano Cliente)
DB_PASSWORD=pegar-acá-otra-contraseña

# Dónde vive cada cosa, vistas desde la otra. Sin la barra final.
IA_INFERENCIA_URL=http://ip-del-servidor-ia:8001
CLIENTE_API_URL=http://ip-del-servidor-cliente:8000
FRONTEND_ORIGIN=http://ip-del-servidor-cliente:8080
ENTRENADOR_ORIGIN=http://ip-del-servidor-ia:8003
```

Para generar el secreto:

```bash
openssl rand -hex 32
```

Qué pasa si alguna queda mal:

| Variable | Si queda mal |
|---|---|
| `JWT_SECRET` distinto entre planos | El login entra bien y **después todo responde 401**. Es el síntoma raro a reconocer. |
| `IA_INFERENCIA_URL` | Los análisis fallan al pedirle detecciones al modelo. Su valor por defecto (`http://localhost:8001`) **no sirve en el servidor**: dentro del contenedor `localhost` es el propio contenedor. |
| `CLIENTE_API_URL` | No se puede entrar al entrenador: su login no llega a quien valida las cuentas. |
| `FRONTEND_ORIGIN` / `ENTRENADOR_ORIGIN` | El navegador bloquea los pedidos por CORS si alguien consume la API desde otra página. |

Una más, si la carpeta `datos/` tiene que pertenecer a un usuario que no sea el
1000: `cliente-api` corre con `${UID}:${GID}`, y esas dos **no están exportadas
en bash por defecto**, así que caen al 1000 salvo que las pongas vos:

```bash
echo "UID=$(id -u)" >> despliegue/.env
echo "GID=$(id -g)" >> despliegue/.env
```

---

## 4. Servidor **con** GPU (el que entrena)

El archivo base ya está preparado para GPU: construye con CUDA y reserva la
placa. No hace falta ningún override.

```bash
docker compose -f despliegue/compose.ia.yml up -d --build
```

Eso levanta los cuatro servicios del plano IA: `ia-inferencia` (8001), la API de
entrenamiento (8002, solo en 127.0.0.1), el worker y `entrenador-web` (8003).

Comprobá que la placa llegó adentro del contenedor:

```bash
curl -s localhost:8002/salud
```

Y, ya con sesión iniciada en el entrenador, la pantalla de Entrenamientos
habilita o no la opción GPU según `GET /dispositivos`. Si dice que no hay,
el motivo que muestra distingue los tres casos posibles: falta la placa, falta
un torch con CUDA, o falta el acceso del contenedor al dispositivo.

Para escalar a varios entrenamientos en paralelo:

```bash
docker compose -f despliegue/compose.ia.yml up -d --scale ia-entrenamiento-worker=2
```

---

## 5. Servidor **sin** GPU

Hay dos casos y conviene no confundirlos.

### 5.1. Solo analiza (lo habitual)

Es el caso del servidor que recibe los modelos ya entrenados. **No necesita
ningún override**, porque `ia-inferencia` no reserva la placa: se levanta ese
servicio solo.

```bash
docker compose -f despliegue/compose.ia.yml up -d --build ia-inferencia
```

Con eso y el plano Cliente (sección 6) el sistema analiza. La única diferencia
contra una máquina con placa es la velocidad del análisis, que es CPU puro;
`TAMANO_LOTE_MAX: 4` en el compose ya es el óptimo medido en CPU.

### 5.2. Además entrena, en CPU

Entrenar sin placa funciona, pero tarda horas. Si igual hace falta, va el
override, y **van los dos `-f`**:

```bash
docker compose -f despliegue/compose.ia.yml -f despliegue/compose.ia.cpu.yml up -d --build
```

El override hace dos cosas: saca la reserva de la placa (sin eso el `up` falla
antes de arrancar) y construye con las ruedas de torch para CPU, que son varios
GB más chicas.

Ojo con una cosa al encolar un trabajo: si se pide `dispositivo: gpu` en una
máquina sin placa, el trabajo queda **fallido en el momento**, antes de copiar
el dataset. Es a propósito: entrenar en CPU sin avisar serían horas de cómputo
que nadie pidió.

---

## 6. Plano Cliente (en las dos recetas)

```bash
docker compose -f despliegue/compose.cliente.yml up -d --build
```

Levanta PostgreSQL + PostGIS, `cliente-api` (8000) y `cliente-web` (8080).

Después, **una sola vez**, las cuentas del equipo:

```bash
docker compose -f despliegue/compose.cliente.yml run --rm cliente-api python crear_usuarios.py
```

Es seguro repetirlo: si el usuario ya existe, actualiza sus datos en vez de
duplicarlo. Las contraseñas que trae el script son temporales y hay que
avisarle la suya a cada uno por fuera del repo.

### Si la base ya existía

Postgres corre los archivos de `base-datos/init/` **una sola vez**, al crear el
volumen. Sobre una base que ya existe hay que aplicar a mano los que falten.
Son idempotentes, así que no pasa nada si se corren de más:

```bash
cd /ruta/al/repo
for f in 03_segmentacion 04_escala 05_cascada; do
  docker compose -f despliegue/compose.cliente.yml exec -T db \
    psql -U agrovision -d agrovision < project/servicios/base-datos/init/$f.sql
done
```

---

## 7. Llevar los modelos al servidor que analiza

Esta es la parte que reemplaza a "entrenar en el servidor": se entrena en la
máquina con placa y se copian los pesos. **Los `.pt` de PyTorch son agnósticos
del dispositivo**: un modelo entrenado en una RTX 3080 carga y detecta igual en
un torch sin CUDA. Lo que cambia es la velocidad, no el resultado.

### Qué hay adentro de `datos/modelos/`

```
datos/modelos/
├── activo/              ← lo que lee ia-inferencia en cada pedido
│   ├── best.pt          6,5 MB
│   └── version.txt      qué versión está activa
├── train-3/             la semilla
├── v_f70593930326/      ~8 MB cada versión: best.pt, meta.json,
├── v_a9672dfb6cb2/      evaluacion.json, results.csv y los PNG
└── v_730cc1730dc1/      de Ultralytics
```

**El detalle que más confunde:** `activo/` es una **copia** del `.pt`, no un
enlace a la carpeta de la versión. Copiar solo `v_xxxx/` no activa nada.

### Armar el comprimido (en la máquina que entrenó)

Dos opciones, según qué quieras llevar:

```bash
cd /ruta/al/repo

# A) El registro completo (~38 MB): el entrenador del servidor va a poder
#    mostrar las métricas y los gráficos de cada versión, y activar otra.
sudo tar czf modelos-$(date +%Y%m%d).tar.gz -C datos modelos

# B) Solo lo que hace falta para analizar (6,5 MB).
sudo tar czf modelo-activo-$(date +%Y%m%d).tar.gz -C datos modelos/activo
```

El `sudo` es porque las carpetas las creó el contenedor y pertenecen a `root`.
`tar` preserva dueño y permisos, que es lo que querés.

Verificá qué versión estás llevando antes de mandarla:

```bash
V=$(cat datos/modelos/activo/version.txt) && echo "activo: $V" && \
  python3 -c "import json; m=json.load(open('datos/modelos/$V/meta.json')); \
  print('tarea:', m['tarea'], '| entrenó en:', m['dispositivo'], '|', m['metricas'])"
```

Sale algo así, y lo que importa mirar es `tarea` (si es `segment`, el servidor
va a dibujar manchas) y el `map50_95_mascara`, que es el que dice qué tan bien
sigue el contorno a la mancha:

```
activo: v_730cc1730dc1
tarea: segment | entrenó en: gpu | {'epoca_mejor': 146, ..., 'map50_95_mascara': 0.0731}
```

### Copiarlo y desplegarlo (en el servidor)

```bash
scp modelos-20261102.tar.gz usuario@servidor:/tmp/
```

Y allá:

```bash
cd /ruta/al/repo

# 1. Descomprimir sobre datos/. Pisa activo/ y agrega las versiones nuevas.
sudo tar xzf /tmp/modelos-20261102.tar.gz -C datos

# 2. Comprobar que llegó lo que esperabas
cat datos/modelos/activo/version.txt
ls datos/modelos/

# 3. Listo: NO hay que reiniciar nada.
```

El paso 3 no es un olvido. `ia-inferencia` **abre el archivo en cada pedido**,
así que reemplazar `activo/best.pt` surte efecto en el análisis siguiente sin
reiniciar el contenedor.

### Comprobar que el modelo anda en CPU

```bash
docker compose -f despliegue/compose.ia.yml exec ia-inferencia python -c "
import torch; from ultralytics import YOLO
print('CUDA disponible:', torch.cuda.is_available())
m = YOLO('/datos/modelos/activo/best.pt')
print('tarea:', m.task, '| clases:', list(m.names.values()))
"
```

Tiene que decir `CUDA disponible: False` y mostrar la tarea y las clases. Si la
tarea es `segment`, el mapa va a dibujar manchas; si es `detect`, puntos.

También lo reporta la API:

```bash
curl -s localhost:8001/modelo
```

### Si preferís activar desde el entrenador

Copiando el registro completo (opción A), no hace falta tocar `activo/` a mano:
entrás a `entrenador-web` del servidor, vas a Modelos y le das activar a la
versión que quieras. Eso reescribe `activo/` por vos.

---

## 8. Verificación final

```bash
curl -s localhost:8000/salud     # cliente-api
curl -s localhost:8001/salud     # ia-inferencia
curl -s localhost:8002/salud     # ia-entrenamiento-api (solo donde esté)
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080   # cliente-web
curl -s -o /dev/null -w '%{http_code}\n' localhost:8003   # entrenador-web
```

Los `/salud` responden `{"estado":"ok", ...}` y los dos fronts, `200`.

Después, entrar a `cliente-web` con una de las cuentas y correr un análisis
sobre un ortomosaico chico: es lo único que prueba el camino completo (login →
teselas → modelo → PostGIS → mapa).

---

## 9. Problemas comunes

| Síntoma | Causa |
|---|---|
| El login entra y después **todo** responde 401 | `JWT_SECRET` no coincide entre los dos planos. |
| No se puede entrar al entrenador | El plano Cliente está caído, o `CLIENTE_API_URL` no llega a él. Es el único que emite tokens. |
| `could not select device driver "nvidia"` | Falta el NVIDIA Container Toolkit, o es una máquina sin placa y hay que sumar `compose.ia.cpu.yml`. |
| `devices: []` no saca la reserva de GPU | Compose **suma** las listas al fusionar archivos. Por eso el override usa `!override`, que necesita Compose v2.24+. |
| El análisis falla al detectar | `IA_INFERENCIA_URL` quedó en el default, que apunta al propio contenedor. |
| Las columnas nuevas no existen | La base ya existía y faltan las migraciones de la sección 6. |
| El mapa marca puntos y no manchas | Está activo un modelo `detect` (por ejemplo la semilla). Activar uno `segment`. |
| El puerto 8080 "parece ocupado" | Un contenedor puede *exponer* un puerto sin *publicarlo*. Lo que ocupa el puerto del host es lo que tenga `0.0.0.0:<puerto>->` adelante en `docker ps`. |
