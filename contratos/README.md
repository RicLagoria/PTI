# contratos

Fuente de verdad compartida entre los tres planos: la forma de las APIs
(OpenAPI) y la taxonomía canónica de clases. Cambiar algo acá es un cambio de
contrato, no un detalle interno de un servicio.

Archivos previstos:

- `clases.json` — lista canónica de clases. **El orden de la lista es el índice
  que va en las etiquetas YOLO**, así que solo se puede cambiar por el final:
  - las clases nuevas se agregan al final;
  - una clase se puede retirar solo si está al final. Los aportes ya subidos
    siguen sirviendo: al armar cada entrenamiento se descartan sus cajas de las
    clases retiradas. Así se retiraron `camino` y `lodazal` (octubre de 2026).
  - Reordenar o borrar una clase del medio cambia lo que significa cada índice
    e invalida los aportes ya subidos.
- `ia-inferencia.openapi.yaml`
- `ia-entrenamiento.openapi.yaml`

Diseño completo: [docs/arquitectura.md](../docs/arquitectura.md).
