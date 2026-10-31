# entrenador-web

Plano Entrenador. SPA en React (mismo stack que `cliente-web`: HeroUI +
Tailwind) para subir aportes etiquetados con labelme, lanzar entrenamientos,
seguir su progreso y activar versiones del modelo.

No tiene backend propio: habla directo con la API de `ia-entrenamiento` y se
sirve desde el plano IA (`despliegue/compose.ia.yml`, puerto 8003). Su nginx
reenvía `/api/*` a `ia-entrenamiento-api`.

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
