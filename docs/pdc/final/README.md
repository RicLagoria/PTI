# Certificación de Entrega — Entrega Final: Integración, demo en vivo y defensa oral

> Qué evalúa esta entrega: el sistema completo funcionando de punta a punta, y que cada
> integrante pueda explicar cualquier parte del proyecto.

## Datos generales

| Campo | Valor |
|---|---|
| **Grupo N°** | 1 |
| **Integrantes** | Santiago Godoy · Jorge Iriarte · Ricardo Lagoria |
| **Temática y caso de uso** | Agricultura de precisión: detección de malezas en caña de azúcar a partir de ortomosaicos de drone |
| **Repositorio de GitHub** | https://github.com/RicLagoria/PTI (rama `pdc/final`) |
| **Tag / Release de esta entrega** | `v6-final` |
| **Fecha de entrega** | _dd/mm/aaaa_ |

## Checklist de la entrega

| Requisito | Cumple | Justificación breve / evidencia |
|---|---|---|
| Las seis capas (infraestructura, comunicación, middleware, seguridad, patrones/escalabilidad) funcionan integradas. | **Sí** | Todo corre junto con `compose.dev.yml` + `compose.pdc.yml` (§Integración): una sola entrada HTTPS, roles en las dos APIs, descubrimiento de la IA, cola de entrenamiento y réplicas balanceadas de `cliente-api`. Probado de punta a punta: login por HTTPS, análisis en vivo, 403 por rol, failover y carga con k6. |
| La demo en vivo fue ensayada de punta a punta antes de la presentación. | _Completar_ | Guion con tiempos, responsables y plan B: [`guion-demo.md`](guion-demo.md). |
| El repositorio tiene el README, la carpeta /docs por módulo y un tag/release por entrega. | **Sí** | Índice en [`docs/pdc/README.md`](../README.md), una carpeta por módulo con certificado, informe y evidencias, y tags `v0-plan` a `v6-final`. |
| Cada integrante puede explicar cualquier parte del proyecto, no solo la propia. | _Completar_ | Preguntas probables con respuestas cortas por módulo: [`preguntas-defensa.md`](preguntas-defensa.md). En la presentación, cada uno expone módulos que no programó. |
| Se repasaron las devoluciones de entregas anteriores y se resolvieron los pendientes señalados. | **Sí** | Ver §Pendientes resueltos. |

## Integración: qué capa aporta qué

| Módulo | Qué aporta al sistema final | Dónde |
|---|---|---|
| 1 · Arquitectura | Dos planos (Cliente e IA) y servicios con una responsabilidad cada uno | `docs/arquitectura.md`, `entrega-1-arquitectura/` |
| 2 · Infraestructura | Un contenedor por servicio, un compose por plano y volúmenes para los datos | `despliegue/` |
| 3 · Comunicación | REST síncrono hacia la IA, SSE hacia el navegador, cola asíncrona para entrenar y reclamo atómico | `entrega-3-comunicacion/` |
| 4 · Middleware | Contratos OpenAPI verificados y descubrimiento de servicios con latido y TTL | `contratos/`, `registro-servicios` |
| 5 · Seguridad | JWT, roles lector/colaborador/admin, HTTPS, límite de login, backup probado y STRIDE | `entrega-5-seguridad/` |
| 6 · Patrones y escalabilidad | Gateway (proxy y fachada), mensaje-comando, réplicas balanceadas, pool de conexiones, k6 y failover | `entrega-6-patrones/` |

## Pendientes resueltos de entregas anteriores

| Entrega | Pendiente | Resolución |
|---|---|---|
| 5 | No había autorización por rol | Tres roles, controlados en las dos APIs y reflejados en los dos fronts |
| 5 | Sin cifrado en tránsito | Gateway HTTPS con redirección 80 → 443; los puertos internos no se publican |
| 5 | Sin recuperación probada | `backup.sh` / `restaurar.sh` y una prueba que compara las filas de cada tabla |
| 5 | Sin informe de amenazas | `informe-amenazas.md` (STRIDE) |
| 4 | El registro y el entrenador chocaban en el puerto 8003 del host | El registro pasó al 8004 del host (adentro sigue en el 8003) |

## Evidencia adicional

- Índice y comandos para reproducir todo: [`docs/pdc/README.md`](../README.md)
- Presentación: _pegar acá el link de las diapositivas_

---

### Espacio para el docente

| Nota | Corregido por | Fecha de corrección |
|---|---|---|
| ____ / 10 | | __ /__ / ____ |

**Observaciones:**
