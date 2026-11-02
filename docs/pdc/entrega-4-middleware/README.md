# Certificación de Entrega — Entrega 4: Contratos de interfaz y descubrimiento de servicios

**Módulo 4 — Middleware y componentes distribuidos**

> Qué evalúa esta entrega: que el sistema esté desacoplado por contrato explícito, no por
> coincidencia entre los integrantes.

## Datos generales

| Campo | Valor |
|---|---|
| **Grupo N°** | 1 (Godoy Cabrera, Santiago Abel · Iriarte Chamorro, Jorge Manuel · Lagoria, Ricardo) |
| **Tag / Release de esta entrega** | `v4-middleware` |
| **Fecha de entrega** | 02/11/2026 |

## Checklist de la entrega

| Requisito | Cumple | Justificación breve / evidencia |
|---|---|---|
| Los contratos de interfaz (API REST) entre componentes están documentados formalmente. | **Sí** | Un contrato OpenAPI por servicio en [`contratos/`](../../../contratos): `ia-inferencia` (3 operaciones), `ia-entrenamiento` (17), `cliente-api` (15) y `registro-servicios` (5). Cada servicio sirve además su Swagger en `/docs`. Ver [informe §2](informe.md#2-contratos-de-interfaz). |
| Cada componente puede modificarse internamente sin romper el contrato hacia los demás. | **Sí** | El motor de `ia-inferencia` pasó de detección a segmentación y su contrato solo **sumó** campos opcionales (1.0.0 → 1.1.0): `cliente-api` siguió andando sin cambios. Hay una regla de versionado escrita para el consumidor (menor = compatible, mayor = rompe). Ver [informe §3](informe.md#3-evolución-sin-romper-versionado). |
| Hay un mecanismo de descubrimiento de servicios implementado (aunque sea simplificado). | **Sí** | Servicio propio `registro-servicios`: cada instancia de `ia-inferencia` se anuncia sola y late cada 5 s; si deja de latir, vence por TTL. `cliente-api` pide las instancias vivas por nombre, reparte entre ellas, pasa a otra si una cae y, si el registro cae, vuelve a la URL fija. **Ejecutado:** [`salida-descubrimiento.txt`](salida-descubrimiento.txt). Ver [informe §4](informe.md#4-descubrimiento-de-servicios). |
| El desacople está verificado: no depende de que los integrantes se hayan puesto de acuerdo informalmente. | **Sí** | [`verificar_contratos.py`](../../../contratos/verificar_contratos.py) compara el `/openapi.json` real de cada servicio con su contrato y falla si difieren. **Ejecutado** con los cuatro servicios: encontró una ruta sin documentar (`/salud` de `ia-entrenamiento`), se corrigió y ahora pasan las 40 operaciones; también detecta las tres rupturas simuladas. [`salida-contratos.txt`](salida-contratos.txt). Ver [informe §5](informe.md#5-verificación-del-desacople). |

## Evidencia adicional

Documentación de la API:

- Contratos OpenAPI (fuente de verdad): <https://github.com/RicLagoria/PTI/tree/pdc/santiago-godoy/contratos>
- Reglas de contrato y versionado: [`contratos/README.md`](../../../contratos/README.md)
- Swagger interactivo de cada servicio (con el entorno levantado):
  `cliente-api` <http://localhost:8000/docs> · `ia-inferencia` <http://localhost:8001/docs> ·
  `ia-entrenamiento` <http://localhost:8002/docs> · `registro-servicios` <http://localhost:8003/docs>

Cómo reproducir (sin Docker, con las dependencias de los servicios instaladas):

```bash
python docs/pdc/entrega-4-middleware/demo_contratos.py
python docs/pdc/entrega-4-middleware/demo_descubrimiento.py
```

- Informe descriptivo y técnico: [`informe.md`](informe.md)
- Salidas obtenidas el 02/11/2026: [`salida-verificacion-inicial.txt`](salida-verificacion-inicial.txt) ·
  [`salida-contratos.txt`](salida-contratos.txt) · [`salida-descubrimiento.txt`](salida-descubrimiento.txt)
- Carpeta en GitHub: <https://github.com/RicLagoria/PTI/tree/pdc/santiago-godoy/docs/pdc/entrega-4-middleware>

---

### Espacio para el docente

| Nota | Corregido por | Fecha de corrección |
|---|---|---|
| ____ / 10 | | __ /__ / ____ |

**Observaciones:**
