# Certificación de Entrega — Entrega 1: Propuesta de Arquitectura

**Módulo 1 — Introducción a la programación distribuida**

> Qué evalúa esta entrega: que el grupo entendió el marco conceptual antes de escribir la primera
> línea de código.

## Datos generales

| Campo | Valor |
|---|---|
| **Grupo N°** | _Completar_ |
| **Integrantes** | Godoy Cabrera, Santiago Abel · Iriarte Chamorro, Jorge Manuel · Lagoria, Ricardo Augusto |
| **Temática** | Agricultura de precisión — detección de malezas en caña de azúcar con imágenes de dron (AgroVision) |
| **Dominio** | <https://github.com/RicLagoria/PTI> |
| **Área / Sector empresarial** | Agrotecnología (agtech) |
| **Tag / Release de esta entrega** | `v1-arquitectura` |
| **Fecha de entrega** | 02/10/2026 |

## Checklist de la entrega

| Requisito | Cumple | Justificación breve / evidencia |
|---|---|---|
| El problema a resolver está descripto con claridad (qué hace el sistema y para quién). | **Sí** | Analiza ortomosaicos de dron con YOLOv8 y marca en un mapa dónde hay malezas, para productores, agrónomos y administradores. Ver [informe §1](informe.md#1-problema-a-resolver). |
| La temática elegida está justificada, incluyendo su correlato real en el mercado de trabajo. | **Sí** | Problema real en Tucumán (60 % de la caña del país, sobreuso de herbicida de USD 80–150/ha). Mismo patrón que DroneDeploy, Taranis, See & Spray y Auravant. Ver [informe §2](informe.md#2-justificación-de-la-temática-y-correlato-en-el-mercado-laboral). |
| Vista Lógica: están identificadas las clases/entidades principales del dominio. | **Sí** | Usuario, Ortomosaico, Tesela, Análisis, Celda, Detección y ModeloIA, con su diagrama de clases. Ver [informe §3](informe.md#3-vista-lógica). |
| Vista de Desarrollo: hay una primera idea de cómo se organizará el código (módulos/servicios). | **Sí** | Servicios `front-react` (+ gateway nginx) y `back` (API + procesamiento YOLO), cada uno con su Dockerfile, con capas de presentación, API y procesamiento. Ver [informe §4](informe.md#4-vista-de-desarrollo). |
| Vista de Procesos: se identificó al menos un punto de concurrencia o sincronización esperado. | **Sí** | P1: dos análisis simultáneos sobre la misma imagen pisan `detecciones.json`. Además P2–P4, con ideas de solución a evaluar. Ver [informe §5](informe.md#5-vista-de-procesos). |
| Vista Física: se planteó cuántos nodos/máquinas tendrá el sistema y cómo se relacionan. | **Sí** | 2 nodos (front + gateway y back) más un volumen compartido, conectados por HTTP, con ideas de crecimiento. Ver [informe §6](informe.md#6-vista-física). |
| Escenarios (+1): hay al menos un caso de uso concreto descripto atravesando las cuatro vistas. | **Sí** | CU-01 "Analizar un lote", con una tabla por vista, y CU-02 "Análisis concurrente del mismo lote". Ver [informe §7](informe.md#7-escenarios-1). |

## Evidencia adicional

Diagramas, informe e infografía en GitHub, en una carpeta por entrega:

- Informe 4+1 con diagramas: [`docs/pdc/entrega-1-arquitectura/informe.md`](informe.md)
- Infografía descriptiva y técnica: [`docs/pdc/assets/infografia.png`](../assets/infografia.png)
- Presentación: _pegar link_
- Carpeta de documentos: <https://github.com/RicLagoria/PTI/tree/master/docs/pdc>

---

### Espacio para el docente

| Nota | Corregido por | Fecha de corrección |
|---|---|---|
| ____ / 10 | | __ /__ / ____ |

**Observaciones:**
