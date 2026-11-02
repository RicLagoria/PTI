import { useEffect, useState } from "react";

/**
 * El worker manda una estimación cada pocos segundos. Entre una y otra, el valor
 * se sigue moviendo en el navegador (baja si es tiempo restante, sube si es
 * tiempo transcurrido), y cada estimación nueva lo corrige. `clave` cambia con
 * cada actualización del worker.
 */
export function useCuentaRegresiva(segundos: number | undefined, clave: string | undefined, sentido: 1 | -1 = -1) {
  const [base, setBase] = useState<{ segundos: number; recibido: number } | null>(null);
  const [ahora, setAhora] = useState(() => Date.now());

  useEffect(() => {
    setBase(segundos === undefined ? null : { segundos, recibido: Date.now() });
    // Solo cuando llega una actualización nueva del worker
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, segundos === undefined]);

  useEffect(() => {
    if (!base) return;
    const reloj = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(reloj);
  }, [base]);

  if (!base) return undefined;
  return Math.max(0, base.segundos + (sentido * (ahora - base.recibido)) / 1000);
}
