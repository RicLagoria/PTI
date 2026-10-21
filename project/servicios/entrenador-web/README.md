# entrenador-web

Plano Entrenador. SPA en React (mismo stack que `cliente-web`: HeroUI +
Tailwind) para subir aportes etiquetados con labelme, lanzar entrenamientos,
seguir su progreso y activar versiones del modelo.

No tiene backend propio: habla directo con la API de `ia-entrenamiento` y se
sirve desde el plano IA (`despliegue/compose.ia.yml`, puerto 8003). Su nginx
reenvía `/api/*` a `ia-entrenamiento-api`.

## Pantallas

- **Aportes** (`/`): subir un ZIP de labelme y ver los ya guardados, con el
  conteo de cajas por clase. Si la API rechaza un aporte, muestra qué
  etiquetas no existen o qué archivos fallaron.
- **Entrenamientos** (`/entrenamientos`): elegir aportes, épocas, tamaño de
  imagen y pesos de partida, y encolar. Los trabajos en cola o en curso se
  siguen en vivo por SSE (`/entrenamientos/{id}/stream`).
- **Modelos** (`/modelos`): versiones del registro con sus métricas, la
  diferencia de mAP50-95 contra la activa y el botón para activar otra.

No hay login: cualquiera que llegue a la página puede entrenar y activar
modelos. Mientras sea así, el puerto no debería quedar expuesto fuera de la red
del equipo.

## Desarrollo

Vite 7 necesita Node 20 o más nuevo. Con la API corriendo en el puerto 8002:

```bash
npm install
npm run dev     # http://localhost:5173, el proxy de vite.config.ts manda /api a localhost:8002
npm run build   # tsc -b && vite build
npm run lint
```

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
