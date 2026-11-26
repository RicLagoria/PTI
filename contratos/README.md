# contratos

Fuente de verdad compartida entre los tres planos: la forma de las APIs
(OpenAPI) y la taxonomía canónica de clases. Cambiar algo acá es un cambio de
contrato, no un detalle interno de un servicio.

Archivos:

- `clases.json` — lista canónica de clases. **El orden de la lista es el índice
  que va en las etiquetas YOLO**, así que solo se puede cambiar por el final:
  - las clases nuevas se agregan al final;
  - una clase se puede retirar solo si está al final. Los aportes ya subidos
    siguen sirviendo: al armar cada entrenamiento se descartan sus etiquetas de
    las clases retiradas. Así se retiraron `camino` y `lodazal` (octubre de 2026).
  - Reordenar o borrar una clase del medio cambia lo que significa cada índice
    e invalida los aportes ya subidos.
- `ia-inferencia.openapi.yaml` — teselas en píxeles locales → detecciones.
- `ia-entrenamiento.openapi.yaml` — aportes, entrenamientos y registro de modelos.
- `cliente-api.openapi.yaml` — la API que consume `cliente-web` (login,
  ortomosaicos, teselas, análisis, historial y exportación).
- `registro-servicios.openapi.yaml` — descubrimiento de servicios: alta y
  latido de instancias, y consulta de las vivas por nombre lógico.

## Versionado

Cada contrato tiene `info.version` y el servicio declara **la misma** en su
`FastAPI(version=...)`. Se sigue versionado semántico desde el punto de vista
del consumidor:

| Cambio | Ejemplo | Versión |
|---|---|---|
| Agrega algo opcional; un consumidor viejo sigue andando | campo nuevo en una respuesta, ruta nueva, parámetro opcional | **menor** (1.0.0 → 1.1.0) |
| Rompe a un consumidor existente | quitar o renombrar una ruta, un campo o un parámetro; volver obligatorio uno opcional | **mayor** (1.1.0 → 2.0.0) |
| Solo redacción o ejemplos | descripción más clara | **parche** (1.1.0 → 1.1.1) |

Un cambio mayor se acuerda con los dueños de los consumidores **antes** de
mergearlo, y se anota en el PR.

## Verificación

`verificar_contratos.py` compara cada servicio en marcha (su `/openapi.json`,
que FastAPI genera del código real) contra su contrato de esta carpeta, y sale
con código 1 si difieren en versión, rutas, métodos, parámetros o código de
éxito:

```bash
python contratos/verificar_contratos.py \
  ia-inferencia=http://localhost:8001 ia-entrenamiento=http://localhost:8002 \
  registro-servicios=http://localhost:8003 cliente-api=http://localhost:8000
```

Correrlo antes de abrir un PR que toque un `server.py`. Si falla, o se
arregla el código, o se actualiza el contrato **y** su versión según la tabla.

Diseño completo: [docs/arquitectura.md](../docs/arquitectura.md).
