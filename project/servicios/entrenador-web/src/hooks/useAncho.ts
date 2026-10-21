import { useEffect, useRef, useState } from "react";

/** Ancho en píxeles de un contenedor, actualizado cuando cambia de tamaño. */
export function useAncho<T extends HTMLElement>(inicial = 600) {
  const ref = useRef<T>(null);
  const [ancho, setAncho] = useState(inicial);

  useEffect(() => {
    const elemento = ref.current;
    if (!elemento) return;
    const observador = new ResizeObserver(([entrada]) => setAncho(Math.round(entrada.contentRect.width)));
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);

  return [ref, ancho] as const;
}
