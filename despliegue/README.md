# despliegue

Archivos de Docker Compose, uno por plano, para poder desplegar cada uno en una
máquina distinta.

Archivos previstos:

- `compose.ia.yml` — servidor remoto: `ia-inferencia`, `ia-entrenamiento` (API
  y worker) y `entrenador-web`.
- `compose.cliente.yml` — `cliente-api` y `cliente-web`.
- `compose.dev.yml` — todo en una sola máquina, para desarrollo.
- `nginx/` — configuración del proxy de cada plano.
- `.env.ejemplo`

Los volúmenes viven en `datos/`, en la raíz del repo, ignorado por git.

Diseño completo: [docs/arquitectura.md](../docs/arquitectura.md).
