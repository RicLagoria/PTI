# entrenador-web

Plano Entrenador. SPA en React (mismo stack que `cliente-web`: HeroUI +
Tailwind) para subir aportes etiquetados con labelme, lanzar entrenamientos,
seguir su progreso y activar versiones del modelo.

No tiene backend propio: habla directo con la API de `ia-entrenamiento` y se
sirve desde el mismo nginx del plano IA.

Diseño completo: [docs/arquitectura.md](../../../docs/arquitectura.md).
