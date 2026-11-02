# entrenador-web

Plano Entrenador. SPA en React (mismo stack que `cliente-web`: HeroUI +
Tailwind) para subir aportes etiquetados con labelme, lanzar entrenamientos,
seguir su progreso y activar versiones del modelo.

No tiene backend propio: habla directo con la API de `ia-entrenamiento` y se
sirve desde el plano IA (`despliegue/compose.ia.yml`, puerto 8003). Su nginx
reenvía `/api/*` a `ia-entrenamiento-api` y `/auth/*` a `cliente-api`, que es
quien valida el login (ver abajo).

## Pantallas

- **Aportes** (`/`): subir un ZIP de labelme y ver los ya guardados, con el
  conteo de etiquetas por clase. Si la API rechaza un aporte, muestra qué
  etiquetas no existen o qué archivos fallaron; si lo acepta pero algo quedó
  raro, lo avisa (un aporte sin contornos solo sirve para entrenar cajas, y uno
  etiquetado con rectángulos tiene contornos que no aportan forma).
- **Entrenamientos** (`/entrenamientos`): elegir aportes, épocas, paciencia,
  tamaño de imagen, pesos de partida y **dónde entrenar (CPU o GPU)**, y
  encolar. Los trabajos en cola o en curso se siguen en vivo por SSE
  (`/entrenamientos/{id}/stream`).

  Los pesos de partida son los que deciden qué se entrena: `yolov8n-seg.pt`
  contornos, `yolov8n.pt` cajas. La opción GPU se habilita según
  `GET /dispositivos`, y cuando no está disponible se muestra qué falta (ver el
  README de `ia-entrenamiento`).

  La paciencia es el early stopping: las épocas son un tope y la corrida corta
  sola si el mAP no mejora en esa cantidad seguida. Cuando eso pasa, la tarjeta
  del trabajo dice en qué época cortó, porque si no el número de épocas pedidas
  no coincide con la curva.
- **Modelos** (`/modelos`): versiones del registro con su tarea (contornos o
  cajas) y sus métricas, la diferencia de mAP50-95 contra la activa y el botón
  para activar otra. Activar una de cajas o una de contornos cambia lo que ve el
  cliente en el mapa: puntos o manchas.

## Login

Las cuentas son las **mismas** que las del sitio de análisis: la tabla
`usuarios` de PostgreSQL, las que carga `cliente-api/app/crear_usuarios.py`. No
hay registro ni cambio de contraseña acá.

Quien valida usuario y contraseña es `cliente-api`, no el plano IA. El front le
pega a `/auth/login`, que su nginx (y el proxy de vite en desarrollo) reenvía
allá, así que en el navegador sigue siendo el mismo origen y no hay CORS de por
medio. Lo que vuelve es un JWT con el perfil adentro, y de ahí en adelante todo
pedido a `ia-entrenamiento-api` lo lleva: en el header `Authorization`, o como
`?token=` en los dos casos que no pueden mandar headers (el SSE del progreso,
que es un EventSource, y los gráficos de cada modelo, que son `<img src>`).

`ia-entrenamiento-api` solo **verifica la firma** de ese token con el mismo
`JWT_SECRET` (ver su `api/auth.py`): no conoce las cuentas ni toca la base. Por
eso el plano IA necesita tener la variable con el mismo valor que el plano
Cliente; si no coinciden, el login sale bien y después todo responde 401. El
front trata ese 401 volviendo al login con un aviso, así que el síntoma es que
te saca de la sesión apenas entrás.

Dos consecuencias del reparto, a tener en cuenta:

- Para entrar al entrenador, **el plano Cliente tiene que estar levantado**. El
  plano IA no puede emitir un token por su cuenta.
- Entra cualquier usuario de la tabla, sin distinción de rol: `admin` y
  `colaborador` pueden entrenar y activar modelos igual. La columna `rol` se
  muestra en el menú de usuario y no restringe nada.

## Desarrollo

Vite 7 necesita Node 20 o más nuevo. Hacen falta **las dos** APIs: la de
entrenamiento en el 8002 y `cliente-api` en el 8000, que es la que atiende el
login (sin ella se ve la pantalla de login pero no se puede entrar).

```bash
npm install
npm run dev     # http://localhost:5173; el proxy de vite.config.ts manda /api a localhost:8002 y /auth a localhost:8000
npm run build   # tsc -b && vite build
npm run lint
```

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
