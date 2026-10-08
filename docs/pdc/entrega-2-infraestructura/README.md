# Certificación de Entrega — Entrega 2: Infraestructura

**Módulo 2 — Arquitectura de infraestructura**

> Qué evalúa esta entrega: que la separación física entre nodos sea real y justificada, no
> interfaces sin backend.

## Datos generales

| Campo | Valor |
|---|---|
| **Grupo N°** | _Completar_ (Godoy – Iriarte – Lagoria) |
| **Tag / Release de esta entrega** | `v2-infraestructura` |
| **Fecha de entrega** | 09/10/2026 |

## Checklist de la entrega

| Requisito | Cumple | Justificación breve / evidencia |
|---|---|---|
| Hay al menos dos nodos separados funcionando (contenedores o procesos distintos). | **Sí** | `front` (nginx: SPA + gateway, imagen propia) y `back` (FastAPI + YOLOv8, imagen propia), en contenedores distintos, comunicados por la red interna de Docker. Ver [informe §1](informe.md#1-qué-se-entrega). |
| La separación es real: cada nodo puede iniciarse/detenerse de forma independiente. | **Sí** | Script [`probar-nodos.sh`](probar-nodos.sh): con la API detenida el front sirve y `/api` da 502; con el front detenido la API responde por dentro. Se corrigió el gateway para que encuentre a la API aunque se recree con otra IP. Ver [informe §2](informe.md#2-la-separación-es-real). |
| Se identificó el modelo de ejecución elegido (cliente-servidor / P2P / microservicios). | **Sí** | Cliente-servidor en capas: navegador → gateway → servidor de aplicación (API + modelo de IA). |
| El modelo de ejecución elegido está justificado en función del caso de uso. | **Sí** | Archivos de GB y minutos de CPU por análisis se centralizan en el servidor. P2P no aplica porque no hay pares que compartan recursos. Microservicios no se justifica hoy: el backend es un único servicio. Ver [informe §3](informe.md#3-modelo-de-ejecución-elegido-cliente-servidor-en-capas). |
| El README explica cómo levantar el entorno localmente (paso a paso). | **Sí** | [README principal → Inicio rápido](../../../README.md#inicio-rápido): requisitos, clonado, pesos del modelo, `docker compose up -d --build`, operación de cada nodo y una prueba con un GeoTIFF sintético. |

## Evidencia adicional

- URL local de la aplicación: <http://localhost:8080> (API a través del gateway: <http://localhost:8080/api/imagenes>)
- Informe descriptivo y técnico: [`docs/pdc/entrega-2-infraestructura/informe.md`](informe.md)
- Prueba de nodos: [`probar-nodos.sh`](probar-nodos.sh) · salida: [`salida-prueba.txt`](salida-prueba.txt)
- Captura del mapa con datos servidos por la API: [`evidencia-mapa.jpg`](evidencia-mapa.jpg)
- Carpeta en GitHub: <https://github.com/RicLagoria/PTI/tree/master/docs/pdc/entrega-2-infraestructura>

---

### Espacio para el docente

| Nota | Corregido por | Fecha de corrección |
|---|---|---|
| ____ / 10 | | __ /__ / ____ |

**Observaciones:**
