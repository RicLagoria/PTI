# Certificación de Entrega — Entrega 5: Seguridad y confiabilidad

**Módulo 5 — Seguridad y confiabilidad en entornos distribuidos**

> Qué evalúa esta entrega: que el grupo haya pensado qué pasa cuando algo falla o es atacado,
> no solo el camino feliz.

## Datos generales

| Campo | Valor |
|---|---|
| **Grupo N°** | 1 (Godoy – Iriarte – Lagoria) |
| **Tag / Release de esta entrega** | `v5-seguridad` |
| **Rama** | `pdc/final` |

## Checklist de la entrega

| Requisito | Cumple | Justificación breve / evidencia |
|---|---|---|
| Hay autenticación de usuarios implementada. | **Sí** | `cliente-api/app/auth.py`: login contra PostgreSQL (`POST /auth/login`), contraseñas con bcrypt, JWT HS256 que vence a las 12 h. Todo endpoint salvo `/salud` y el login exige token. `ia-entrenamiento` verifica la firma del mismo JWT. |
| Hay autorización / control de acceso implementado (no todos los usuarios pueden todo). | **Sí** | Tres roles (§A), controlados en las **dos APIs** con `requiere_rol()`; los fronts esconden lo que el rol no puede hacer. Prueba: [`probar_roles.py`](probar_roles.py) → [evidencia](evidencias/roles.txt). |
| La comunicación entre componentes está cifrada en tránsito (HTTPS/TLS). | **Sí** | Gateway nginx con TLS 1.2/1.3 en el 443 y redirección `80 → 443` (§B). Los puertos internos (API, IA, base, registro) ya no se publican. [Evidencia](evidencias/tls.txt). |
| Hay un mecanismo de replicación o recuperación ante fallos implementado y probado. | **Sí** | Backup y restauración de la base con `pg_dump` / `pg_restore`, más una prueba que restaura en una base aparte y compara las filas (§C). Además: healthchecks, `restart` y réplicas de `cliente-api` con failover en el gateway. [Evidencia](evidencias/recuperacion.txt). |
| Se incluyó un informe corto de amenazas consideradas (qué se protegió y de qué). | **Sí** | [`informe-amenazas.md`](informe-amenazas.md): análisis STRIDE, qué se mitigó y qué queda como riesgo aceptado. |

## A. Autorización por rol

El rol viaja dentro del JWT, así que verificarlo no consulta la base. Cada nivel incluye lo del anterior:

| Acción | `lector` | `colaborador` | `admin` |
|---|---|---|---|
| Ver ortomosaicos, mapa, análisis, historial, estadísticas y exportar | Sí | Sí | Sí |
| Subir ortomosaicos y correr análisis nuevos | — | Sí | Sí |
| Subir aportes, derivar escalas, encolar y cancelar entrenamientos | — | Sí | Sí |
| Borrar aportes y activar un modelo | — | — | Sí |

- Código: `requiere_rol()` en [`cliente-api/app/auth.py`](../../../project/servicios/cliente-api/app/auth.py) y en [`ia-entrenamiento/api/auth.py`](../../../project/servicios/ia-entrenamiento/api/auth.py).
- La base solo acepta esos tres valores: [`base-datos/init/06_roles.sql`](../../../project/servicios/base-datos/init/06_roles.sql).
- El rol se chequea **antes** de buscar la imagen: un lector recibe `403` y no se entera de qué imágenes existen.
- Cuenta de demo: `lector` (alta en `crear_usuarios.py`).

## B. Cifrado en tránsito

- [`despliegue/compose.pdc.yml`](../../../despliegue/compose.pdc.yml) se suma a `compose.dev.yml` y agrega un **gateway** ([`nginx/gateway.conf`](../../../despliegue/nginx/gateway.conf)), que es la única puerta de entrada.
- Certificado autofirmado generado con `despliegue/pdc/generar-certificado.sh`. La clave no va a git.
- Cabeceras de seguridad: HSTS, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` y `Referrer-Policy`.
- **Límite de login**: 5 intentos por minuto por IP, con una ráfaga de 5; pasado eso responde `429`, para frenar la fuerza bruta.
- Dentro de la red de Docker el tráfico sigue en HTTP: esa red no es accesible desde afuera (ver el informe de amenazas).

## C. Recuperación ante fallos

| Falla | Qué la cubre |
|---|---|
| Se pierde o se corrompe la base | `pdc/backup.sh` (`pg_dump`) y `pdc/restaurar.sh` (`pg_restore`). |
| Se cuelga un proceso | `healthcheck` en `db`, `cliente-api` e `ia-inferencia`, con `restart: unless-stopped`. |
| Se cae una réplica de `cliente-api` | El gateway reintenta en otra (`proxy_next_upstream`), así que el usuario no ve el error. |
| Se cae el worker de entrenamiento a mitad de un trabajo | La cola en disco de `ia-entrenamiento` retoma el trabajo cuando el worker vuelve. |

**Prueba de recuperación** (`bash despliegue/pdc/probar-recuperacion.sh`):

1. Cuenta las filas de las tablas principales.
2. Hace un backup y lo restaura en una base aparte (`agrovision_prueba`), sin tocar la real.
3. Compara las filas tabla por tabla y mide el tiempo de restauración.

Resultado: las 4 tablas coinciden, en unos 40 s. [Salida](evidencias/recuperacion.txt).

## Cómo reproducir todo

```bash
bash despliegue/pdc/generar-certificado.sh
docker compose -f despliegue/compose.dev.yml -f despliegue/compose.pdc.yml up -d --build
python docs/pdc/entrega-5-seguridad/probar_roles.py
bash despliegue/pdc/probar-recuperacion.sh
```

---

### Espacio para el docente

| Nota | Corregido por | Fecha de corrección |
|---|---|---|
| ____ / 10 | | __ /__ / ____ |

**Observaciones:**
