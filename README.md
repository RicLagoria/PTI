# PTI — Plataforma de Detección de Malezas en Caña de Azúcar

**Proyecto Tecnológico Integrador | Ingeniería en Informática | Universidad Blas Pascal**

Plataforma open source de agricultura de precisión para la detección automática de malezas en cultivos de caña de azúcar (Tucumán, Argentina) mediante imágenes RGB de dron, deep learning y datos satelitales abiertos.

# Backend
entrenamiento de IA en volov8


1-crear una carpeta con las imagenes que se usaran para entrenar
2-utilizar la herramienta labelme para etiquetar cada imagen, al finalizar se generara una estructura de carpetas que se usara para entrenar la isa
3-actuzlizar la carpeta dataset dentro de entrenar ai
4-agregar una imagen etiquetada dentro de dataset/images/val para validar el entrenamiento
5-ejecutar train.py y seguido predict.py para verificar visualmente lo que de la IA


python Python 3.9.13

herramienta de etiquetado de imagen 
pip install labelme
labelme

requerimientos :
annotated-types==0.7.0
beautifulsoup4==4.15.0
certifi==2026.7.22
charset-normalizer==3.5.1
click==8.1.8
colorama==0.4.6
coloredlogs==15.0.1
contourpy==1.3.0
cycler==0.12.1
filelock==3.19.1
flatbuffers==25.12.19
fonttools==4.60.2
fsspec==2025.10.0
gdown==5.2.2
humanfriendly==10.0
idna==3.19
ImageIO==2.37.2
imgviz==1.7.6
importlib_resources==6.5.2
Jinja2==3.1.6
kiwisolver==1.4.7
labelImg==1.8.6
labelme==5.10.1
labelme2yolo==0.4.0
lazy-loader==0.5
loguru==0.7.3
lxml==6.1.1
MarkupSafe==3.0.3
matplotlib==3.9.4
mpmath==1.3.0
natsort==8.4.0
networkx==3.2.1
numpy==2.0.2
nvidia-ml-py==13.610.43
onnxruntime==1.19.2
opencv-python==5.0.0.93
osam==0.2.5
packaging==26.3
pillow==11.3.0
polars==1.36.1
polars-runtime-32==1.36.1
protobuf==6.33.6
psutil==7.2.2
pydantic==2.13.4
pydantic_core==2.46.4
pyparsing==3.3.2
PyQt5==5.15.11
PyQt5-Qt5==5.15.2
PyQt5_sip==12.17.1
pyreadline3==3.5.6
PySocks==1.7.1
python-dateutil==2.9.0.post0
PyYAML==6.0.3
requests==2.32.5
scikit-image==0.24.0
scipy==1.13.1
six==1.17.0
soupsieve==2.8.4
sympy==1.14.0
tifffile==2024.8.30
torch==2.8.0
torchvision==0.23.0
tqdm==4.70.0
typing-inspection==0.4.2
typing_extensions==4.16.0
ultralytics==8.4.121
ultralytics-thop==2.1.6
urllib3==2.6.3
win32_setctime==1.2.0
zipp==3.23.1






---

## Equipo

| Integrante | Rol |
|---|---|
| Briguera, Octavio | ML Engineer / Integración |
| Juarez, Carlos Nahuel | ML Engineer / QA |
| Godoy Cabrera, Santiago Abel | Frontend / Visualización |
| Guerrero, Lautaro | ML Engineer / Datos |
| Iriarte Chamorro, Jorge Manuel | Backend / DevOps |
| Lagoria, Ricardo Augusto | Backend / DevOps |

**Docente tutor:** Gencarelli, Oscar Luis
**Institución:** Universidad Blas Pascal — Córdoba, Argentina
**Versión:** 1.0 | Mayo 2026

---

## Descripción

El sistema procesa imágenes de vuelo RGB mediante OpenDroneMap, detecta malezas con modelos YOLOv8/v11 entrenados con datos locales, calcula índices de vegetación visibles (ExG, VARI, GLI, MGRVI) y enriquece el análisis con datos de Sentinel-2 (GEE), humedad de suelo (SMAP L4) y pronóstico meteorológico (Open-Meteo / NASA POWER).

La salida es un JSON georreferenciado por parcela con un mapa de prescripción variable de herbicidas, validado agronómicamente por técnicos del INTA Famaillá.

**Resultado esperado:** reducción del 20–35 % en el consumo de herbicidas por campaña.
**Infraestructura:** 100 % open source | costo < USD 200 usando tiers académicos gratuitos.

---

## Pipeline

```
Vuelo RGB
    |
    v
OpenDroneMap --> GeoTIFF ortomosaico + DSM/DTM
    |
    v
Preprocesamiento (OpenCV + Rasterio) --> tiles 1024x1024 px
    |
    v
YOLOv8/v11 (detección) + DeepLabV3+ (segmentación) + ResNet-18 (estadio fenológico)
    |
    v
Índices de vegetación (ExG, VARI, GLI, MGRVI)
    |
    v
Enriquecimiento APIs (Sentinel-2 / SMAP L4 / Open-Meteo / NASA POWER)
    |
    v
Motor de reglas YAML --> prescripción variable por parcela
    |
    v
API REST (FastAPI) + Dashboard web (Leaflet) + exportación GeoJSON / PDF
```

---

## Stack tecnológico

| Capa | Tecnología | Licencia |
|---|---|---|
| Fotogrametría | OpenDroneMap | AGPL-3.0 |
| Detección | YOLOv8/v11 (Ultralytics) | AGPL-3.0 |
| Segmentación | DeepLabV3+ / U-Net (SMP) | MIT |
| Geoprocesamiento | Rasterio, GDAL, GeoPandas | BSD/MIT |
| Teledetección | Google Earth Engine + Sentinel-2 | Académico |
| Clima / Suelo | Open-Meteo, NASA POWER, SMAP L4 | CC BY 4.0 |
| Backend | FastAPI + Celery + Redis | MIT/BSD |
| Base de datos | PostgreSQL 15 + PostGIS 3.4 | PostgreSQL |
| Frontend | React + Leaflet.js | MIT |
| MLOps | MLflow + CVAT | Apache 2.0 |
| Infraestructura | Docker Compose + GitHub Actions | Apache 2.0 |

---

## Estructura del repositorio

```
PTI/
├── data/                   # Scripts de descarga y preprocesamiento de datos
│   ├── labeling/           # Configuración CVAT y scripts de etiquetado
│   └── raw/                # (ignorado por .gitignore — datos locales)
├── ml/                     # Entrenamiento, evaluación y exportación de modelos
│   ├── train/
│   ├── eval/
│   └── models/             # Pesos exportados (.onnx, .pt)
├── geo/                    # Procesamiento ODM, índices de vegetación, GEE
│   ├── odm/
│   ├── indices/
│   └── satellite/
├── backend/                # FastAPI + Celery + motor de reglas
│   ├── api/
│   ├── rules/              # Reglas agronómicas en YAML
│   └── workers/
├── frontend/               # Dashboard React + Leaflet
├── infra/                  # Docker Compose, variables de entorno, CI/CD
│   ├── docker-compose.yml
│   └── .github/workflows/
├── tests/                  # Suite pytest — cobertura objetivo >= 70 %
├── docs/                   # Documentación técnica y agronómica
└── README.md
```

---

## Inicio rápido

El código que corre hoy es el MVP en `project/mvp/`: dos nodos (contenedores) independientes,
orquestados con Docker Compose.

| Nodo | Servicio | Puerto | Qué hace |
|---|---|---|---|
| `front` | nginx + SPA React | `8080` (único expuesto) | Sirve la interfaz y hace de *gateway*: reenvía `/api/*` a la API |
| `back` | FastAPI + uvicorn + YOLOv8 | `8000` (solo red interna) | Carga de ortomosaicos, teselas del mapa y análisis en vivo (SSE) |

### Requisitos previos

- Docker Desktop (o Docker Engine >= 24) con Docker Compose v2
- Git
- ~6 GB libres para las imágenes (torch en su variante CPU)

### Levantar el entorno paso a paso

```bash
# 1. Clonar el repositorio y entrar a la carpeta del MVP
git clone https://github.com/RicLagoria/PTI.git
cd PTI/project/mvp

# 2. Poner los pesos del modelo donde los busca el backend (MODEL_PATH=/data/modelo/best.pt).
#    La carpeta data/ es el volumen compartido y no se versiona.
mkdir -p data/modelo
cp train-3/weights/best.pt data/modelo/best.pt

# 3. Construir y levantar los dos nodos en segundo plano
#    (la primera vez tarda varios minutos: descarga torch CPU y compila el front)
docker compose up -d --build

# 4. Verificar que están corriendo
docker compose ps
```

- Interfaz: <http://localhost:8080> (usuario de prueba del front: `admin` / `1234`).
- API a través del gateway: <http://localhost:8080/api/imagenes>.
- La API tarda ~15 s en arrancar (carga torch y el modelo). Mientras tanto `/api` responde 502.

### Operar cada nodo por separado

```bash
docker compose stop back      # detiene solo la API (el front sigue sirviendo; /api responde 502)
docker compose start back     # la vuelve a levantar sin tocar el front
docker compose stop front     # detiene solo el front/gateway (la API sigue viva en la red interna)
docker compose start front
docker compose logs -f back   # logs de un nodo
docker compose down           # baja todo (los datos quedan en data/)
```

La prueba completa de independencia de nodos está en
`docs/pdc/entrega-2-infraestructura/probar-nodos.sh`.

### Probar sin un ortomosaico real

Se puede generar un GeoTIFF sintético dentro del contenedor de la API y subirlo por el gateway:

```bash
docker compose exec back python -c "import numpy as np, rasterio; from rasterio.transform import from_bounds; img=np.random.default_rng(0).integers(40,190,(3,1300,1300),dtype='uint8'); d=rasterio.open('/tmp/prueba.tif','w',driver='GTiff',width=1300,height=1300,count=3,dtype='uint8',crs='EPSG:4326',transform=from_bounds(-65.201,-26.801,-65.2,-26.8,1300,1300)); d.write(img); d.close()"
docker compose cp back:/tmp/prueba.tif ./prueba.tif
curl -X POST --data-binary @prueba.tif "http://localhost:8080/api/imagenes?nombre=prueba.tif"
```

---

## Fases del proyecto

| Fase | Período | Hito principal |
|---|---|---|
| F1 | Meses 1-2 | Entorno Docker funcional + dataset baseline 200 imgs |
| F2 | Meses 3-5 | Demo E2E con 2 especies — pipeline completo de punta a punta |
| F3 | Meses 6-8 | mAP@0.5 >= 0,75 sobre dataset local (>= 800 imgs) |
| F4 | Meses 9-10 | Dashboard + API documentada + validación agronómica INTA |
| F5 | Mes 11 | Cobertura tests >= 70 % + documentación + defensa |

---

## Especies objetivo (EEAOC, Avance 2023)

| Especie | Nombre común | Frecuencia en Tucumán |
|---|---|---|
| Cynodon dactylon | Gramilla | 49 % |
| Tithonia tubaeformis | Pasto cubano | 64 % (emergente) |
| Sorghum halepense | Sorgo de Alepo | ~30 % |
| Sicyos polyacanthus | Tupúlo | ~35 % |
| Cyperus rotundus | Cebollín | 23 % |

---

## Convenciones de trabajo

- **Ramas:** `main` protegida. Feature branches con prefijo de módulo:
  `ml/`, `geo/`, `api/`, `frontend/`, `infra/`
- **Pull requests:** revisión obligatoria de al menos un integrante distinto al autor
- **Tests:** ningún merge a `main` sin al menos un test que pase en CI
- **Commits:** mensajes en inglés, formato `tipo(scope): descripción`
  — ejemplo: `feat(ml): add YOLOv8 training pipeline`
- **Reducción de alcance:** vertical (menos especies o menos imágenes),
  nunca horizontal (no se saltean etapas del pipeline)

---

## Contribuir

Este es un proyecto académico cerrado. El código se publica bajo licencia AGPL-3.0 para permitir la replicación por otras instituciones del NOA. Si sos investigador o técnico del INTA/EEAOC y querés colaborar, abrí un issue o contactá al equipo.

---

## Licencia

AGPL-3.0 — ver [LICENSE](LICENSE) para el texto completo.

---

## Referencias clave

- IPAAT (2024). Reporte final de zafra 2024.
- EEAOC / Revista Avance (2023). Relevamiento de malezas en caña de azúcar en Tucumán.
- Jocher et al. (2023). YOLOv8 — Ultralytics.
- Larrazabal et al. (2024). Site-Specific Prescription Maps for Sugarcane Weed Control. Land, 13(11).
- Sharma et al. (2024). Comparative performance of YOLO variants for weed detection. Smart Ag Tech, 9.
