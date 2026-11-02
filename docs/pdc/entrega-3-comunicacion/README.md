# Certificación de Entrega — Entrega 3: Comunicación síncrona y asíncrona

**Módulo 3 — Comunicación y sincronización en sistemas distribuidos**

> Qué evalúa esta entrega: que el grupo entienda cuándo corresponde cada semántica de comunicación,
> no solo que el sistema "funcione".

## Datos generales

| Campo | Valor |
|---|---|
| **Grupo N°** | 1 (Godoy Cabrera, Santiago Abel · Iriarte Chamorro, Jorge Manuel · Lagoria, Ricardo) |
| **Tag / Release de esta entrega** | `v3-comunicacion` |
| **Fecha de entrega** | 02/11/2026 |

## Checklist de la entrega

| Requisito | Cumple | Justificación breve / evidencia |
|---|---|---|
| Hay un canal de comunicación síncrono funcionando entre componentes (ej. REST/gRPC). | **Sí** | REST/HTTP en dos tramos: `cliente-web → cliente-api` (login, subida, teselas, metadatos) y `cliente-api → ia-inferencia` (`POST /detectar`: teselas en JPEG, cajas en JSON). El emisor espera la respuesta porque la necesita para seguir. Ver [informe §2](informe.md#2-canal-síncrono-rest-sobre-http). |
| Hay un canal de comunicación asíncrono funcionando entre componentes (ej. cola de mensajes). | **Sí** | Dos usos del mismo patrón de cola en disco con estado consultable: el análisis de un ortomosaico (`POST /imagenes/{id}/analisis` → `202` y `GET` de progreso) y la cola de entrenamientos de `ia-entrenamiento` (API encola, worker consume). Ver [informe §3](informe.md#3-canal-asíncrono-trabajo-en-segundo-plano-con-estado-en-disco). |
| Está justificado por qué se usó cada semántica en cada punto del sistema. | **Sí** | Tabla por punto del sistema: lo corto y necesario para continuar es síncrono; lo que dura minutos y no bloquea al usuario es asíncrono. Se explica también por qué no se usó un broker (RabbitMQ/Redis). Ver [informe §4](informe.md#4-qué-semántica-en-cada-punto-y-por-qué). |
| Se identificó un caso de concurrencia concreto (ej. dos escrituras simultáneas sobre el mismo recurso). | **Sí** | Caso **P1**, ya anticipado en la Entrega 1: dos análisis simultáneos sobre el mismo ortomosaico escriben el mismo `detecciones.json` y gana el último. Ver [informe §5.1](informe.md#51-el-problema-p1). |
| Ese caso de concurrencia está resuelto y la solución puede demostrarse (no solo describirse). | **Sí** | Lock exclusivo por imagen (`flock`) más escritura atómica del JSON: el segundo análisis recibe `409` en vez de pisar al primero. Código en `cliente-api/app/bloqueo.py` y `tareas.py`; demostración con [`probar-concurrencia.sh`](probar-concurrencia.sh). Ver [informe §5](informe.md#5-caso-de-concurrencia-p1-dos-análisis-simultáneos-sobre-la-misma-imagen) y el [estado de verificación](informe.md#7-estado-de-verificación-y-límites). |

## Evidencia adicional

Cómo reproducir el caso de concurrencia resuelto (con el entorno levantado y un usuario creado):

```bash
docker compose -f despliegue/compose.dev.yml up -d --build
USUARIO=RicLagoria CONTRASENA='...' IMAGEN=ruta/al/ortomosaico.tif \
  bash docs/pdc/entrega-3-comunicacion/probar-concurrencia.sh
```

Resultado esperado: un pedido responde `202` y el otro `409`; el análisis aceptado termina en
`completado`; `detecciones.json` queda válido y completo. Detalle en el
[informe](informe.md#6-cómo-reproducirlo).

- Informe descriptivo y técnico: [`docs/pdc/entrega-3-comunicacion/informe.md`](informe.md)
- Script de prueba: [`probar-concurrencia.sh`](probar-concurrencia.sh)
- Código de la solución: [`bloqueo.py`](../../../project/servicios/cliente-api/app/bloqueo.py),
  [`tareas.py`](../../../project/servicios/cliente-api/app/tareas.py) y los endpoints de
  [`server.py`](../../../project/servicios/cliente-api/app/server.py)
- Carpeta en GitHub: <https://github.com/RicLagoria/PTI/tree/master/docs/pdc/entrega-3-comunicacion>

---

### Espacio para el docente

| Nota | Corregido por | Fecha de corrección |
|---|---|---|
| ____ / 10 | | __ /__ / ____ |

**Observaciones:**
