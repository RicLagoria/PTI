# Plataforma Open Source de Agricultura de Precisión para la Detección de Malezas en Caña de Azúcar (Tucumán, Argentina)

**Proyecto Tecnológico Integrador (PTI)**
Universidad Blas Pascal – Ingeniería en Informática – Córdoba, Argentina

---

## 1. Información General del Proyecto

- **Título del proyecto:** Plataforma Open Source de Agricultura de Precisión para la Detección de Malezas en Caña de Azúcar (Tucumán, Argentina)
- **Integrantes:**
  - Briguera, Octavio
  - Juarez, Carlos Nahuel
  - Godoy Cabrera, Santiago Abel
  - Guerrero, Lautaro
  - Iriarte Chamorro, Jorge Manuel
  - Lagoria, Ricardo Augusto
- **Docente tutor:** Gencarelli, Luis Oscar
- **Institución:** Universidad Blas Pascal – Ingeniería en Informática – Córdoba, Argentina
- **Fecha:** Segunda entrega (actualización sobre la Primera Entrega del 21/05/2026)
- **Versión:** 2.0
- **Repositorio (GitHub):** https://github.com/RicLagoria/PTI

---

## 2. Resumen Ejecutivo

Se presenta el diseño de una plataforma 100 % open source de monitoreo de campos mediante drones, orientada a la caña de azúcar en Tucumán, Argentina, que integra fotogrametría con drones RGB, visión artificial para la **detección de malezas** y la **predicción de rendimiento**, e inteligencia artificial para el análisis integral de los datos generados. El sistema procesa imágenes de vuelo RGB mediante OpenDroneMap y PyTorch, enriquece los resultados con imágenes satelitales Sentinel‑2 (Copernicus/Google Earth Engine), datos de humedad edafológica (SMAP L4) y pronóstico meteorológico (Open‑Meteo/NASA POWER), y produce un JSON georreferenciado por parcela con recomendaciones agronómicas accionables (mapas de prescripción variable de herbicidas).

El resultado esperado es una reducción del 20‑35 % en el consumo de herbicidas por campaña, sobre la base de antecedentes locales documentados por la EEAOC y el INTA Famaillá, junto con una mejora en la anticipación de rendimiento por lote. El proyecto está planificado para 11 meses, con un equipo de seis estudiantes de Ingeniería en Informática, un presupuesto de infraestructura cloud inferior a USD 200 y utilizando exclusivamente herramientas de licencia libre.

---

## 3. Planteo del Problema

### 3.1 Contexto del problema

Tucumán concentra el 60 % de la producción nacional de caña de azúcar. Según datos del IPAAT, en la zafra 2024 se molieron 17.062.495 toneladas sobre 294.470 hectáreas cosechables, con 14 ingenios activos y 228 días de molienda. Las exportaciones del NOA totalizaron 407.539 toneladas. A nivel nacional, la producción alcanzó 24.383.000 toneladas (Centro Azucarero Argentino, 2025).

### 3.2 Situación actual

Las malezas constituyen el principal factor biótico limitante del rendimiento en este cultivo. La literatura internacional reporta pérdidas de entre el 20 % y el 72 % según especie y estadio (Chauhan & Srivastava, 2002). A nivel local, la EEAOC documentó caídas de hasta 21,44 t/ha por competencia con pasto cubano (*Tithonia tubaeformis*) a densidades inferiores a 5 plantas/m² (Revista Avance, EEAOC, 2023). El relevamiento fitosociológico publicado por Cabrera et al. (2020) en La Cocha (Tucumán) identificó especies con dominancia creciente en lotes de mayor edad de corte.

Según el último relevamiento de la EEAOC (Avance 2023), las especies más frecuentes en la provincia son:

| Nombre común | Nombre científico | Familia | Frecuencia (EEAOC) |
|---|---|---|---|
| Grama bermuda / Gramilla | *Cynodon dactylon* (L.) Pers. | Poaceae | 49 % |
| Pasto cubano / Yuyo cubano | *Tithonia tubaeformis* (Jacq.) Cass. | Asteraceae | 64 % (emergente) |
| Pasto ruso / Sorgo de Alepo | *Sorghum halepense* (L.) Pers. | Poaceae | ~30 % |
| Tupúlo | *Sicyos polyacanthus* Cogn. | Cucurbitaceae | ~35 % |
| Cebollín | *Cyperus rotundus* L. | Cyperaceae | 23 % |

El manejo actual se realiza predominantemente mediante aplicación de herbicidas a tasa uniforme, sin diferenciación espacial por densidad o especie. Esta práctica implica un sobreuso de herbicidas estimado en USD 80‑150/ha por campaña, con impacto económico para el productor y ambiental sobre los suelos y cursos de agua de la cuenca del Río Salí. A esto se suma la falta de herramientas accesibles para estimar de forma temprana el rendimiento esperado por lote, lo que dificulta la planificación de cosecha e insumos.

### 3.3 Antecedentes y brecha tecnológica

El INTA Famaillá conduce ensayos desde 2015 con drones RGB (DJI Phantom 4), combinando OpenDroneMap, QGIS y algoritmos de IA para detección de fallas de siembra (Ing. Ricardo Rodríguez, INTA Informa). La EEAOC trabaja con imágenes Landsat desde 1997 y Sentinel‑2 desde 2015, principalmente para seguimiento de biomasa y área cosechable (Fandos et al., Revista Avance). Sin embargo, ninguno de estos esfuerzos genera un pipeline completo que vincule la imagen del dron con una recomendación de herbicida por parcela —con identificación a nivel de especie y mapa de prescripción variable— ni con una estimación de rendimiento integrada al mismo flujo de datos. Esa es la brecha que cierra el presente proyecto.

### 3.4 Justificación

La combinación de alta disponibilidad de drones RGB de bajo costo, modelos de detección de objetos de última generación (YOLOv8/v11), técnicas de predicción de rendimiento basadas en visión e índices espectrales, y APIs satelitales y climáticas abiertas (GEE, SMAP, Open‑Meteo), hace técnicamente viable —por primera vez— construir este pipeline de forma íntegra con herramientas libres y un presupuesto accesible para instituciones académicas y pequeños/medianos productores del NOA.

---

## 4. Objetivos

### 4.1 Objetivo General

Desarrollar una plataforma open source de agricultura de precisión que, a partir del procesamiento de imágenes RGB de dron, detecte automáticamente la presencia y distribución espacial de malezas, estime el rendimiento esperado por parcela en cultivos de caña de azúcar de Tucumán, y genere mapas de prescripción variable de herbicidas con respaldo agronómico validado por especialistas del INTA.

### 4.2 Objetivos Específicos

- **OE‑01:** Implementar un pipeline de procesamiento fotogramétrico basado en OpenDroneMap para la generación de ortomosaicos georreferenciados a partir de vuelos con drones RGB sobre lotes cañeros de Tucumán.
- **OE‑02:** Construir y etiquetar un dataset local de al menos 500 imágenes de cañaverales tucumanos con bounding boxes y máscaras de segmentación para las especies dominantes relevadas por la EEAOC.
- **OE‑03:** Entrenar y evaluar modelos de detección (YOLOv8/v11) y segmentación semántica (DeepLabV3+) sobre el dataset local, alcanzando un mAP@0.5 ≥ 0,75 y una inferencia menor a 100 ms por tile en CPU.
- **OE‑04:** Calcular índices de vegetación visibles (ExG, VARI, GLI, MGRVI) e integrar datos satelitales de Sentinel‑2 (NDVI, NDWI) y variables edafoclimáticas (SMAP L4, Open‑Meteo, NASA POWER) como capas contextuales del análisis, incluyendo su uso como insumo para la estimación de rendimiento.
- **OE‑05:** Diseñar e implementar un motor de reglas agronómicas declarativas en formato YAML, editable por agrónomos sin modificar código, con validación formal por técnicos del INTA Famaillá.
- **OE‑06:** Construir una API REST (FastAPI) y un dashboard web geoespacial (Leaflet) que permitan visualizar, consultar y exportar los mapas de prescripción y las estimaciones de rendimiento generadas, con latencia end‑to‑end ≤ 12 horas para una parcela de 10 hectáreas.

---

## 5. Alcance del Proyecto

### 5.1 Incluye

- Pipeline fotogramétrico completo desde la ingesta de imágenes de dron hasta la generación de ortomosaicos georreferenciados (OpenDroneMap).
- Módulo de visión artificial para detección y segmentación de malezas por especie (YOLOv8/v11, DeepLabV3+) sobre las cinco especies dominantes relevadas por la EEAOC.
- Módulo de estimación de rendimiento por parcela a partir de índices de vegetación visibles, cobertura de dosel y variables satelitales/edafoclimáticas.
- Enriquecimiento con fuentes abiertas: Sentinel‑2 (NDVI, NDWI, NDRE, NDMI), SMAP L4 (humedad de suelo), Open‑Meteo y NASA POWER (pronóstico y evapotranspiración).
- Motor de reglas agronómicas declarativas (YAML) editable por agrónomos, validado con el INTA Famaillá.
- API REST (FastAPI) y dashboard web geoespacial (Leaflet) para visualización, consulta y exportación de mapas de prescripción y reportes.
- Validación de campo en al menos 3 lotes piloto en Tucumán, con participación de 2‑3 productores.
- Documentación técnica completa y publicación de resultados (póster o paper académico).

### 5.2 No incluye

- Aplicación automatizada de agroquímicos (el sistema genera recomendaciones, no ejecuta pulverización).
- Desarrollo de hardware propio de dron o de cámaras multiespectrales/NIR (se trabaja únicamente con cámaras RGB estándar).
- Comercialización del producto durante la duración del PTI (el proyecto se mantiene en fase académica, open source, sin modelo de negocio activo).
- Cobertura de cultivos distintos a la caña de azúcar en esta primera versión (aunque la arquitectura está pensada para ser extensible).
- Garantía de sustitución del criterio profesional del agrónomo: el sistema es una herramienta de soporte de decisión, no un reemplazo del asesoramiento técnico habilitado.
- Escalado a nivel provincial o comercial durante el desarrollo académico (queda como línea de trabajo futuro).

### 5.3 Business Model Canvas

Aunque el proyecto se desarrolla en el marco académico de un Proyecto Tecnológico Integrador y no persigue fines comerciales inmediatos, se construyó un Business Model Canvas para analizar su viabilidad como iniciativa sostenible a futuro (spin‑off universitario, convenio con INTA/EEAOC, o servicio ofrecido a ingenios y cooperativas).

| Bloque | Contenido |
|---|---|
| **Socios clave** | INTA Famaillá, EEAOC, UBP (cátedra e infraestructura académica), ingenios azucareros de Tucumán, productores piloto, proveedores locales de servicios de vuelo con drones, comunidad open source (OpenDroneMap, Ultralytics) |
| **Actividades clave** | Desarrollo y mantenimiento del pipeline de visión artificial; captura y etiquetado de datasets locales; entrenamiento y validación de modelos; diseño y actualización del motor de reglas agronómicas junto al INTA; vuelos de relevamiento; soporte y capacitación a productores |
| **Recursos clave** | Dataset local etiquetado (imágenes + bounding boxes/máscaras); modelos entrenados (YOLOv8/v11, DeepLabV3+); infraestructura cloud (cómputo, almacenamiento, PostGIS); conocimiento agronómico validado (INTA/EEAOC); equipo de seis estudiantes de Ingeniería en Informática |
| **Propuesta de valor** | Reducción del 20‑35 % en el consumo de herbicidas mediante aplicación de tasa variable; detección temprana de malezas por especie; estimación de rendimiento por parcela; plataforma 100 % open source y de bajo costo (< USD 200 de infraestructura); recomendaciones agronómicas trazables y validadas por especialistas |
| **Relación con clientes** | Acompañamiento técnico directo durante la etapa piloto; capacitación a productores y técnicos; dashboard de autoservicio para consulta de mapas y reportes; canal de soporte vía convenio institucional (INTA/EEAOC/UBP) |
| **Canales** | Dashboard web geoespacial y API REST; convenios institucionales con INTA y EEAOC; difusión académica (publicaciones, defensa del PTI); repositorio público en GitHub |
| **Segmentos de clientes** | Productores cañeros de Tucumán (pequeños y medianos); ingenios azucareros; cooperativas agrícolas del NOA; instituciones de investigación y extensión agropecuaria (INTA, EEAOC); a futuro, otros cultivos del NOA (limón, arándano, frutilla, tabaco, soja, garbanzo) |
| **Estructura de costos** | Infraestructura cloud (< USD 200 durante el PTI); costo de vuelos de relevamiento con drones; tiempo de desarrollo del equipo (recurso académico, sin costo monetario directo); sin costos de licenciamiento (stack 100 % open source/libre) |
| **Fuentes de ingreso** | Durante el PTI: ninguna (proyecto académico sin fines de lucro). Como línea futura: servicios de soporte y capacitación, convenios de transferencia tecnológica con INTA/EEAOC, modelo freemium (dashboard básico gratuito + reportes avanzados pagos), licenciamiento de datasets etiquetados a terceros |

> Se dispone además de una versión visual interactiva del canvas (`canvas_modelo_negocio.html`, entregado como anexo), con el mismo diseño gráfico que el cronograma del punto 11.

---

## 6. Marco Teórico y Tecnológico

El proyecto se apoya en cuatro pilares conceptuales:

1. **Fotogrametría con drones (UAV photogrammetry):** técnica que reconstruye ortomosaicos y modelos digitales de superficie (DSM/DTM) a partir de imágenes RGB solapadas capturadas en vuelo, mediante algoritmos de *Structure from Motion* (SfM). Se implementa con OpenDroneMap, herramienta open source (licencia AGPL‑3.0) ampliamente utilizada en agricultura de precisión (Barbosa Júnior et al., 2022).

2. **Visión artificial para detección de malezas:** el problema de detección y segmentación de malezas en cultivos ha sido abordado con modelos de deep learning como YOLO (You Only Look Once) y arquitecturas de segmentación semántica como DeepLabV3+. Sharma et al. (2024) compararon el desempeño de YOLOv8‑v11 y Faster R‑CNN para múltiples especies de malezas, mientras que Sa et al. (2018) propusieron *WeedMap*, un framework de mapeo semántico de malezas basado en imágenes aéreas multiespectrales. El principal desafío reconocido en la literatura es el problema *green‑on‑green* —la similitud espectral entre el cultivo y la maleza— particularmente relevante en caña de azúcar (Kumar et al., 2023).

3. **Índices de vegetación e integración satelital:** en ausencia de banda NIR en cámaras RGB de bajo costo, se recurre a índices visibles como ExG, VARI, GLI y MGRVI, complementados con productos satelitales gratuitos de Sentinel‑2 (NDVI, NDWI, NDRE, NDMI vía Google Earth Engine) y variables edafoclimáticas de SMAP L4 y NASA POWER. Rocha et al. (2024) evaluaron el monitoreo del crecimiento de caña de azúcar mediante índices de vegetación basados en imágenes RGB de UAV.

4. **Sistemas de soporte a la decisión agronómica:** el motor de reglas declarativo (YAML) se enmarca en el enfoque de *rule‑based decision support systems*, que permite a los agrónomos incorporar y actualizar conocimiento experto sin intervención de desarrolladores, favoreciendo la trazabilidad y validación de las recomendaciones (Larrazabal et al., 2024).

---

## 7. Metodología de Trabajo

El proyecto adopta un enfoque ágil basado en **Scrum**, con sprints alineados a las fases del plan de trabajo (ver punto 11), lo que permite iterar sobre el pipeline de datos, los modelos de visión artificial y el dashboard de forma incremental, validando entregables parciales con el docente tutor y con los referentes técnicos del INTA Famaillá y la EEAOC.

Etapas metodológicas generales:

1. **Relevamiento y definición de requisitos** junto a especialistas agronómicos.
2. **Captura de datos** mediante vuelos piloto en lotes cañeros seleccionados.
3. **Desarrollo iterativo** del pipeline (fotogrametría → visión artificial → enriquecimiento satelital → motor de reglas → API/dashboard), en sprints de 2‑3 semanas.
4. **Validación continua** con datos reales y retroalimentación de agrónomos referentes.
5. **Documentación y cierre** con defensa académica y eventual publicación de resultados.

---

## 8. Análisis de Requerimientos

### 8.1 Requerimientos funcionales

- RF‑01: El sistema debe permitir la carga de imágenes de vuelo con metadatos EXIF/GPS.
- RF‑02: El sistema debe generar ortomosaicos georreferenciados a partir de las imágenes cargadas.
- RF‑03: El sistema debe detectar y clasificar malezas por especie sobre el ortomosaico.
- RF‑04: El sistema debe estimar el rendimiento esperado por parcela a partir de variables de cobertura, vegetación y contexto satelital/climático.
- RF‑05: El sistema debe calcular índices de vegetación visibles por celda georreferenciada.
- RF‑06: El sistema debe integrar datos satelitales (Sentinel‑2) y edafoclimáticos (SMAP, Open‑Meteo, NASA POWER) por parcela.
- RF‑07: El sistema debe aplicar un motor de reglas agronómicas configurable para generar recomendaciones.
- RF‑08: El sistema debe exponer los resultados mediante una API REST y un dashboard web geoespacial.
- RF‑09: El sistema debe permitir exportar mapas de prescripción y reportes (JSON, GeoJSON, PDF).

### 8.2 Requerimientos no funcionales

- RNF‑01: Licenciamiento 100 % libre/open source en todo el stack tecnológico.
- RNF‑02: Latencia end‑to‑end ≤ 12 horas para una parcela de 10 hectáreas.
- RNF‑03: Costo de infraestructura cloud inferior a USD 200 durante el desarrollo del PTI.
- RNF‑04: mAP@0.5 ≥ 0,75 en la detección de malezas sobre el dataset local.
- RNF‑05: Inferencia por tile menor a 100 ms en CPU.
- RNF‑06: Trazabilidad y editabilidad de las reglas agronómicas sin modificar código fuente.
- RNF‑07: Usabilidad del dashboard con un SUS (System Usability Scale) ≥ 70 evaluado con productores reales.

---

## 9. Diseño de la Solución

### 9.1 Arquitectura del pipeline

El flujo completo, desde el vuelo hasta el JSON de salida, se compone de ocho etapas secuenciales ejecutadas en servidor:

| # | Etapa | Descripción |
|---|---|---|
| 1 | Ingesta y validación | Carga de imágenes JPG con EXIF GPS vía FastAPI + Celery; metadatos persistidos en PostgreSQL/PostGIS. |
| 2 | Ortomosaico | OpenDroneMap (Docker, AGPLv3): genera GeoTIFF, DSM, DTM. Resolución de salida: 5 cm/pixel (ajustable). |
| 3 | Preprocesamiento | OpenCV: balance de blanco, normalización, recorte. Rasterio/GDAL: reproyección UTM 20S. Tiling 1024×1024 px. |
| 4 | Inferencia CV | YOLOv8n/s (detección/segmentación de malezas) + DeepLabV3+ para segmentación cultivo/maleza/suelo + ResNet‑18 para estadio fenológico y estimación de rendimiento. |
| 5 | Índices de vegetación | ExG, VARI, GLI, MGRVI por celda 1×1 m sobre máscara de vegetación (umbral ExG > Otsu). |
| 6 | Enriquecimiento APIs | Sentinel‑2 L2A → NDVI, NDWI, NDRE, NDMI (GEE/Copernicus). SMAP L4 → humedad radicular. Open‑Meteo → pronóstico 16 d. NASA POWER → ETo. |
| 7 | Motor de reglas | Reglas declarativas YAML/JSON editables por agrónomos; generación de recomendaciones por parcela. |
| 8 | Persistencia y salida | PostgreSQL/PostGIS + almacenamiento objeto (MinIO). Salida: JSON georreferenciado + WMS + reporte PDF. |

### 9.2 Regla agronómica declarativa (ejemplo YAML)

```yaml
# reglas_malezas.yaml
- id: ctrl_cyn_sorg_macollaje
  condicion:
    cobertura_maleza_pct: { gte: 15 }
    especie: ["Cynodon dactylon", "Sorghum halepense"]
    estadio: ["macollaje", "gran_crecimiento"]
  accion:
    tipo: control_quimico_selectivo
    herbicida: "topramezone 33,6 g i.a./ha + atrazina 0,9 kg i.a./ha"
    ventana_dias: 5
    referencia: "Sanchez Ducca et al., 2020 - Sugar Tech"

- id: alerta_estres_hidrico
  condicion:
    NDWI_mean: { lt: 0.1 }
    SMAP_zona_radicular: { lt: 0.18 }
    precipitacion_7d_mm: { lt: 10 }
  accion:
    tipo: monitoreo_estres_hidrico
    prioridad: media
```

### 9.3 Fragmento del JSON de salida

```json
{
  "id_parcela": "TUC-LCO-0421-A3",
  "estadio_fenologico": { "clase": "gran_crecimiento", "confianza": 0.91 },
  "cobertura_dosel_pct": 82.4,
  "malezas": {
    "cobertura_total_pct": 8.6,
    "categorias_detectadas": [
      { "nombre_cientifico": "Cynodon dactylon",
        "cobertura_pct": 4.1, "n_parches": 27, "confianza_prom": 0.87 },
      { "nombre_cientifico": "Sorghum halepense",
        "cobertura_pct": 2.8, "n_parches": 14, "confianza_prom": 0.81 }
    ]
  },
  "recomendaciones": [{
    "tipo": "control_quimico_selectivo",
    "prioridad": "alta",
    "ahorro_estimado_pct": 71,
    "mapa_prescripcion_url": "/api/v1/parcelas/.../prescription.geojson"
  }]
}
```

---

## 10. Tecnologías Utilizadas

| Componente | Tecnología | Licencia | Función |
|---|---|---|---|
| Fotogrametría | OpenDroneMap | AGPL‑3.0 | Generación de ortomosaico, DSM, DTM |
| Detección de malezas | YOLOv8/v11 (Ultralytics) | AGPL‑3.0 | Detección y segmentación de malezas |
| Segmentación | DeepLabV3+ / U‑Net (SMP) | MIT | Segmentación cultivo/maleza/suelo |
| Geoprocesamiento | Rasterio, GDAL, GeoPandas | BSD/MIT | Manejo de rasters y vectores |
| APIs satelitales | Google Earth Engine, Copernicus DSE | Académico | Sentinel‑2: NDVI, NDWI, NDRE, NDMI |
| Datos hídricos | SMAP L4 (NASA) | Libre | Humedad de suelo (9 km, cada 3 h) |
| Meteorología | Open‑Meteo, NASA POWER | AGPL/CC | Pronóstico 16 d, ETo, histórico |
| Backend/API | FastAPI + Celery | MIT/BSD | Procesamiento asíncrono, OpenAPI |
| Base de datos | PostgreSQL 15 + PostGIS 3.4 | PostgreSQL/GPL | Datos vectoriales y atributos |
| Frontend | Leaflet + plugin QGIS | BSD/GPL | Visualización de mapas y reportes |
| MLOps | MLflow + CVAT | Apache 2.0/MIT | Tracking de experimentos y etiquetado |

---

## 11. Plan de Trabajo

El proyecto se desarrolla en cinco fases sobre el ciclo lectivo marzo‑diciembre 2026, ancladas —además del calendario académico— a las **ventanas reales de vuelo en Tucumán** (fin de verano hasta el 20 de mayo, y primavera desde el 20 de septiembre), ya que fuera de esos períodos las lluvias estivales y la logística de zafra impiden volar con calidad de imagen suficiente. Se dispone además de un diagrama de Gantt interactivo (`cronograma_gantt.html`, entregado como anexo) que distingue **plan original** vs. **avance real** por tarea.

**Estado al 11 de agosto de 2026:** avance global ponderado ≈ 13 % sobre 27 actividades no transversales; 1 actividad completada (relevamiento de requisitos y estado del arte); 6 actividades en ejecución en paralelo; fase en curso F1‑F2 (diseño cerrado, entorno en construcción); próximo hito **H2 — demo end‑to‑end con 2 especies**. Riesgo principal: la ventana de vuelo cierra el 20 de mayo, por lo que si la Campaña de vuelo n.° 1 se pierde, el dataset local no se recupera hasta septiembre y el hito H3 se desplaza en bloque.

| Fase | Período | Actividades principales | Hito de cierre |
|---|---|---|---|
| **F1 · Fundación y diseño** | Mar–Abr | Relevamiento de requisitos y estado del arte (100 %); gestión de convenio INTA Famaillá/EEAOC (45 %); diseño de arquitectura y modelo de datos (90 %); entorno Docker Compose y CI/CD (60 %); dataset baseline con fuentes públicas, 200 img (25 %). | **H1** · Entorno reproducible y arquitectura aprobada — 30/04 |
| **F2 · Campaña de campo y pipeline base** | Abr–Jul | Planificación de vuelos y habilitación ANAC (15 %); Campaña de vuelo n.° 1 en 3 lotes piloto; procesamiento ODM y ortomosaicos; etiquetado en CVAT (500 img, 4 especies); pipeline ETL y persistencia en PostGIS (10 %); demo end‑to‑end con 2 especies. | **H2** · Demo end‑to‑end funcional — 31/07 |
| **F3 · Modelado** | Ago–Oct | Entrenamiento YOLOv8/v11 con validación cruzada; índices de vegetación (ExG, VARI, GLI, MGRVI); segmentación DeepLabV3+/U‑Net; clasificador de estadio fenológico (ResNet‑18); Campaña de vuelo n.° 2 (ampliación a 800 img); reentrenamiento y evaluación final. | **H3** · mAP@0.5 ≥ 0,75 sobre dataset local — 30/10 |
| **F4 · Integración y producto** | Sep–Nov | Conectores a Sentinel‑2/GEE; conectores SMAP, Open‑Meteo y NASA POWER; motor de reglas agronómicas en YAML; API REST (FastAPI) y JSON por parcela; dashboard React + Leaflet; validación agronómica con técnicos del INTA. | **H4** · API documentada y reglas validadas — 27/11 |
| **F5 · Cierre académico** | Nov–Dic | Suite de tests (cobertura ≥ 70 %); documentación técnica y manual de usuario; pruebas con productores en 2‑3 lotes; memoria del PTI y preparación de la defensa. | **H5** · Defensa pública — 18/12 |
| **Transversal · Gestión del proyecto** | Mar–Dic | Reuniones semanales y revisión con el docente tutor (46 % de avance). | — |

Los criterios de éxito cuantitativos de cada fase (mAP, mIoU, latencia, SUS, etc.) se mantienen según lo definido en la versión anterior del plan y quedan reflejados como condición de cierre de cada hito.

---

## 12. Desarrollo e Implementación

*Pendiente de desarrollo.* (A completar durante las fases F2‑F5, una vez avanzada la implementación del pipeline.)

---

## 13. Validación y Resultados

*Pendiente de desarrollo.* Los criterios de validación ya están definidos en el Plan de Trabajo (punto 11) y se completarán con datos reales durante las fases F3 y F4.

---

## 14. Impacto del Proyecto

### 14.1 Beneficio económico para el productor

La literatura reporta ahorros del 20‑35 % en herbicidas para aplicaciones de tasa variable (INTA AgTech; Larrazabal et al., 2024). Para un cañero con 100 ha y un costo anual de control de malezas de USD 80‑150/ha, esto representa un ahorro potencial de USD 1.600‑5.250 por campaña. La identificación y el tratamiento temprano de parches de *Cynodon* y *Sorghum* permite recuperar rendimiento: las pérdidas documentadas llegan a 21,44 t/ha (EEAOC, Avance 2023); a precio de caña 2024 (≈35‑50 USD/t bruta), el upside por hectárea es significativo. Adicionalmente, se reducen las horas‑máquina y la presión selectiva sobre poblaciones de malezas, disminuyendo el riesgo de resistencia a glifosato, documentada en *Sorghum halepense* en Argentina. La estimación temprana de rendimiento, por su parte, aporta valor adicional para la planificación logística de cosecha e insumos.

### 14.2 Escalabilidad

El stack es agnóstico al cultivo. Con el reentrenamiento del modelo de visión computacional, la plataforma es transferible a limón (Tucumán es el primer exportador mundial), arándano, frutilla, tabaco, soja y garbanzo en el NOA, así como a viñedo y olivo en Mendoza. La arquitectura distribuida es escalable a nivel provincial mediante convenios existentes del INTA con FEARCA y universidades nacionales. El repositorio público (AGPL‑3.0) permite que otros grupos del NOA extiendan los resultados sin barreras de licenciamiento.

---

## 15. Conclusiones

*Pendiente de desarrollo.* (A completar en las entregas finales, una vez concluidas las fases de validación y resultados.)

---

## 16. Bibliografía

1. Barbosa Júnior, M. R., et al. (2022). UAVs to Monitor and Manage Sugarcane: Integrative Review. *Agronomy, 12*(3), 661.
2. Cabrera, D. C., Juárez Ansonnaud, R., & Varela, A. E. (2020). Análisis de la comunidad de malezas en dos edades de corte de caña de azúcar. *RANAR, 40*(1), 31‑38.
3. Centro Azucarero Argentino. (2025). *Informe de producción nacional de caña de azúcar*.
4. Chauhan, B. S., & Srivastava, V. (2002). Weed management in sugarcane. En estudios de pérdidas por competencia de malezas.
5. EEAOC / Revista Avance. (2023). *Relevamiento de malezas en caña de azúcar en Tucumán*. Estación Experimental Agroindustrial Obispo Colombres.
6. IPAAT. (2024). *Reporte final de zafra 2024*. Instituto Provincial de Acción Integral para el Azucarero Tucumano. https://www.ipaat.gov.ar
7. Kumar, S., et al. (2023). Concealed nature of weed in sugarcane: Deep Neural Networks for Identifying Small Weed Patches Using Drone Images. *IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing*.
8. Larrazabal, M., et al. (2024). Developing Site‑Specific Prescription Maps for Sugarcane Weed Control Using High‑Spatial‑Resolution Images and LiDAR. *Land, 13*(11), 1751.
9. Olsen, A., et al. (2019). DeepWeeds: A Multiclass Weed Species Image Dataset for Deep Learning. *Scientific Reports, 9*, 2058.
10. Rocha, F., et al. (2024). Evaluation of Sugarcane Crop Growth Monitoring Using Vegetation Indices from RGB‑Based UAV Images. *Agronomy, 14*(9), 2059.
11. Sa, I., et al. (2018). WeedMap: A large‑scale semantic weed mapping framework using aerial multispectral imaging and deep neural network. *Remote Sensing*. arXiv:1808.00100.
12. Sánchez Ducca, A., et al. (2020). Topramezone: New Herbicide Registered in Sugarcane for Post‑emergent Management of Cynodon dactylon in Tucumán, Argentina. *Sugar Tech*.
13. Sharma, A., Kumar, V., & Longchamps, L. (2024). Comparative performance of YOLOv8, YOLOv9, YOLOv10, YOLOv11 and Faster R‑CNN for detection of multiple weed species. *Smart Agricultural Technology, 9*.
14. Toward autonomous weed management systems in sugarcane crops and an assessment of technological readiness. (2026). *npj Artificial Intelligence*.

---

## 17. Anexos

- **Anexo A —** `cronograma_gantt.html`: diagrama de Gantt interactivo del Plan de Trabajo (punto 11), con alternancia entre "Avance real" y "Plan original", franjas de ventana de vuelo viable y calendario agronómico de Tucumán.
- **Anexo B —** `canvas_modelo_negocio.html`: Business Model Canvas interactivo correspondiente al punto 5.3.

*Pendiente de desarrollo:* capturas del dashboard, diagramas de arquitectura (componentes, ER, casos de uso), y ejemplos adicionales de salidas del pipeline.