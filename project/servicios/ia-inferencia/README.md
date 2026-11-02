# ia-inferencia

Plano IA. Recibe teselas y devuelve, en píxeles locales, la caja de cada
detección y —si el modelo activo es de segmentación— el contorno de la mancha.
Sin estado y sin geografía: no conoce el ortomosaico, ni coordenadas, ni
usuarios.

- `app/` — servidor FastAPI y el detector YOLO (sale de `mvp/back/detector.py`).

Endpoints: `GET /salud`, `GET /modelo`, `POST /detectar`.

`GET /modelo` informa `tarea`: `segment` si los pesos activos devuelven
contornos, `detect` si solo dan cajas. Sale del `.pt`, no de una configuración,
y el modelo se lee en cada pedido: activar otra versión en `ia-entrenamiento`
cambia la tarea sin reiniciar este servicio.

Con `segment`, cada detección trae `contorno_local` además de `box_local`. El
contorno viene simplificado con Douglas-Peucker (`TOLERANCIA_SIMPLIFICADO`,
`MAX_VERTICES` en `detector.py`): el borde crudo de una máscara de YOLO tiene
cientos de vértices, casi todos sobre la misma recta, y ese contorno viaja hasta
el navegador y se guarda en la base.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
