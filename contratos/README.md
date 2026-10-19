# contratos

Fuente de verdad compartida entre los tres planos: la forma de las APIs
(OpenAPI) y la taxonomía canónica de clases. Cambiar algo acá es un cambio de
contrato, no un detalle interno de un servicio.

Archivos previstos:

- `clases.json` — lista canónica de clases. **El orden de la lista es el índice
  que va en las etiquetas YOLO**: reordenarla o borrar una clase invalida todos
  los datasets ya subidos. Las clases nuevas se agregan siempre al final.
- `ia-inferencia.openapi.yaml`
- `ia-entrenamiento.openapi.yaml`

Diseño completo: [docs/arquitectura.md](../docs/arquitectura.md).
