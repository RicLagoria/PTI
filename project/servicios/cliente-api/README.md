# cliente-api

Plano Cliente. Dueño de los ortomosaicos y de todo lo geoespacial: conversión a
COG, teselas XYZ para el mapa, grilla de celdas, lectura por ventanas y
georreferenciación de las detecciones. Para analizar le manda teselas a
`ia-inferencia` y une las cajas que vuelven con la celda de origen.

- `app/` — servidor FastAPI (sale de `mvp/back/`: `server.py`, `almacen.py`,
  `predict.py`), más el cliente HTTP de `ia-inferencia` y las estadísticas.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
