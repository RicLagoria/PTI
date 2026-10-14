# ia-inferencia

Plano IA. Recibe teselas y devuelve cajas en píxeles locales. Sin estado y sin
geografía: no conoce el ortomosaico, ni coordenadas, ni usuarios.

- `app/` — servidor FastAPI y el detector YOLO (sale de `mvp/back/detector.py`).

Endpoints: `GET /salud`, `GET /modelo`, `POST /detectar`.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
