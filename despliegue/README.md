# despliegue

Archivos de Docker Compose, uno por plano, para poder desplegar cada uno en una
máquina distinta.

- `compose.ia.yml` — servidor remoto: `ia-inferencia`, `ia-entrenamiento` (API
  y worker) y `entrenador-web`. Construye con CUDA y reserva la GPU.
- `compose.ia.cpu.yml` — override del anterior para una máquina sin placa
  NVIDIA; van los dos `-f`. Ver el comentario de cabecera del archivo.
- `compose.cliente.yml` — `db`, `cliente-api` y `cliente-web`.
- `compose.dev.yml` — para desarrollo: todo en una máquina **menos** el
  entrenamiento, que se suma aparte (ver CLAUDE.md).
- `nginx/` — configuración del proxy de cada plano.

Los volúmenes viven en `datos/`, en la raíz del repo, ignorado por git.

## Lo que los dos planos tienen que compartir

El login del entrenador reutiliza las cuentas del sitio de análisis, y eso ata
los dos planos en dos puntos. Si alguno falla, el síntoma es el mismo: el login
entra bien y después todo responde 401, o no se puede ni entrar.

- **`JWT_SECRET` tiene que valer lo mismo en los dos.** `cliente-api` firma el
  token y `ia-entrenamiento-api` verifica esa firma; nadie más lo comparte. El
  valor por defecto es el de desarrollo y hay que cambiarlo en el servidor, en
  los dos lados a la vez.
- **`CLIENTE_API_URL` (en `entrenador-web`) tiene que llegar a `cliente-api`.**
  Es a dónde su nginx manda el `/auth` del login. El default apunta al puerto
  que `cliente-api` publica en el host, que cubre los dos planos en una misma
  máquina; con el plano Cliente en otro servidor, va su URL.

De ahí se sigue algo que conviene tener presente: **el plano IA no se puede usar
sin el plano Cliente levantado**, porque es el único que puede emitir un token.
El plano IA sí arranca solo (`ia-inferencia` sigue sirviendo análisis), pero
nadie puede entrar al entrenador.

Diseño completo: [docs/arquitectura.md](../docs/arquitectura.md).
