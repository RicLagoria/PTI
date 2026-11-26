# Guion de la demo en vivo (unos 10 minutos)

Ensayarlo entero al menos una vez el día anterior, con la PC que se va a usar.

## Antes de entrar (15 minutos antes)

```bash
docker compose -f despliegue/compose.dev.yml -f despliegue/compose.pdc.yml up -d
docker compose -p agrovision-entrenamiento -f despliegue/compose.ia.yml -f despliegue/compose.ia.cpu.yml up -d ia-entrenamiento-api ia-entrenamiento-worker entrenador-web
docker compose -f despliegue/compose.dev.yml -f despliegue/compose.pdc.yml ps   # todo "healthy" o "Up"
```

Antes de empezar, dejar listo:
- Navegador con dos pestañas: `https://localhost`, ya aceptado el aviso del certificado, y `http://localhost:8003`, el entrenador.
- Dos terminales abiertas en la raíz del repo.
- Un ortomosaico chico a mano. `prueba.tif` ya está cargado.

## Recorrido

| # | Quién | Qué se muestra | Qué se dice (módulo) |
|---|---|---|---|
| 1 | Santiago | `https://localhost`: candado y login como **colaborador** | Todo entra por el gateway con HTTPS (M5, M6) |
| 2 | Santiago | Elegir `510206.tif` y moverse por el mapa | Las teselas salen del COG bajo demanda (M2) |
| 3 | Jorge | **Analizar (en vivo)**: las detecciones aparecen a medida que llegan | REST síncrono hacia la IA y SSE al navegador (M3) |
| 4 | Jorge | Terminal: `curl -sk https://localhost/api/salud` y `docker compose ps` | Contenedores y healthchecks (M2, M5) |
| 5 | Jorge | Contar el registro de servicios: la IA se anuncia sola | Descubrimiento (M4) |
| 6 | Ricardo | Cerrar sesión y entrar como **lector**: no aparecen Subir ni Analizar | Roles (M5) |
| 7 | Ricardo | Terminal: `python docs/pdc/entrega-5-seguridad/probar_roles.py` | El backend devuelve 403 aunque se llame a mano (M5) |
| 8 | Ricardo | Entrenador: encolar un entrenamiento (como colaborador) y ver cómo lo toma el worker | Mensaje-comando con cola (M3, M6) |
| 9 | Ricardo | Terminal: `bash despliegue/pdc/probar-failover.sh` | Balanceo entre 3 réplicas y caída de una sin errores (M6) |
| 10 | Ricardo | Gráfico `docs/pdc/entrega-6-patrones/carga/escalado.png` | 1 contra 3 réplicas: p95, throughput y errores (M6) |

## Si algo falla en vivo

| Problema | Qué hacer |
|---|---|
| El navegador no deja entrar por el certificado | "Avanzado → continuar". Explicar que es autofirmado, propio de la demo |
| El login da 429 | Es el límite anti fuerza bruta: esperar un minuto (y sirve como demo) |
| El análisis tarda | Usar `prueba.tif` (1300 × 1300 px) |
| Algo no levanta | Mostrar las evidencias guardadas en `docs/pdc/*/evidencias` y en `carga/` |

## Al terminar

```bash
docker compose -f despliegue/compose.dev.yml -f despliegue/compose.pdc.yml down
docker compose -p agrovision-entrenamiento -f despliegue/compose.ia.yml -f despliegue/compose.ia.cpu.yml down
```
