# AgroVision en Programación Distribuida y Componentes (PDC)

**Grupo 1:** Santiago Godoy · Jorge Iriarte · Ricardo Lagoria

**Caso:** detección de malezas en caña de azúcar a partir de ortomosaicos de drone.

Cada módulo de la materia tiene su carpeta, con:
- el certificado de entrega (`README.md`);
- el informe, cuando lo hay;
- los scripts y las salidas que sirven de evidencia.

El tag marca el estado del repositorio en cada entrega.

| Módulo | Carpeta | Tag |
|---|---|---|
| 0 · Plan del proyecto | [entrega-0-plan](entrega-0-plan/) | `v0-plan` |
| 1 · Arquitectura (4+1) | [entrega-1-arquitectura](entrega-1-arquitectura/) | `v1-arquitectura` |
| 2 · Infraestructura | [entrega-2-infraestructura](entrega-2-infraestructura/) | `v2-infraestructura` |
| 3 · Comunicación | [entrega-3-comunicacion](entrega-3-comunicacion/) | `v3-comunicacion` |
| 4 · Middleware | [entrega-4-middleware](entrega-4-middleware/) | `v4-middleware` |
| 5 · Seguridad y confiabilidad | [entrega-5-seguridad](entrega-5-seguridad/) | `v5-seguridad` |
| 6 · Patrones y escalabilidad | [entrega-6-patrones](entrega-6-patrones/) | `v6-patrones` |
| Final · Integración y demo | [final](final/) | `v6-final` |

Los PDF de cada entrega están en [`pdf/`](pdf/) y se regeneran con `python docs/pdc/generar_pdfs.py`.

## Levantar el sistema completo (como en la demo)

```bash
# 1. Certificado para HTTPS (una sola vez)
bash despliegue/pdc/generar-certificado.sh

# 2. Plano Cliente con gateway HTTPS: https://localhost
docker compose -f despliegue/compose.dev.yml -f despliegue/compose.pdc.yml up -d --build

# 3. Plano IA (entrenador): http://localhost:8003
docker compose -p agrovision-entrenamiento -f despliegue/compose.ia.yml -f despliegue/compose.ia.cpu.yml up -d --build ia-entrenamiento-api ia-entrenamiento-worker entrenador-web
```

## Scripts de prueba

| Qué prueba | Comando |
|---|---|
| Roles: el lector recibe 403 al escribir | `python docs/pdc/entrega-5-seguridad/probar_roles.py` |
| Backup y restauración de la base | `bash despliegue/pdc/probar-recuperacion.sh` |
| Escalado: carga con k6 a 1 y a 3 réplicas | `bash despliegue/pdc/medir-escalado.sh` y luego `python docs/pdc/entrega-6-patrones/carga/graficar.py` |
| Failover: se cae una réplica con tráfico | `bash despliegue/pdc/probar-failover.sh` |
| Contratos: cada servicio cumple su OpenAPI | `python contratos/verificar_contratos.py` |
