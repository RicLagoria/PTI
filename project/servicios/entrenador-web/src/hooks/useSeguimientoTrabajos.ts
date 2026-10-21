// =====================================
// src/hooks/useSeguimientoTrabajos.ts
// =====================================
import { useEffect, useRef } from "react";
import { seguirTrabajo, type Trabajo } from "../services/EntrenamientoService";

export const estaActivo = (t: Trabajo) => t.estado === "pendiente" || t.estado === "ejecutando";

/**
 * Mantiene abierto un stream SSE por cada trabajo pendiente o en ejecución y
 * avisa cada cambio. Se reabren los que falten cada vez que cambia
 * `generacion` (el caller la incrementa al recargar la lista), así un corte de
 * red se recupera en la siguiente recarga en vez de reconectar en loop.
 */
export function useSeguimientoTrabajos(
  trabajos: Trabajo[],
  generacion: number,
  onCambio: (trabajo: Trabajo) => void,
  onTermino: (trabajo: Trabajo) => void,
  onCorte: () => void
) {
  const abiertos = useRef(new Map<string, EventSource>());
  // Callbacks en refs: cambian en cada render y no deben reabrir los streams
  const callbacks = useRef({ onCambio, onTermino, onCorte });
  callbacks.current = { onCambio, onTermino, onCorte };

  const idsActivos = trabajos.filter(estaActivo).map((t) => t.id).join(",");

  useEffect(() => {
    const activos = new Set(idsActivos ? idsActivos.split(",") : []);

    for (const id of activos) {
      if (abiertos.current.has(id)) continue;
      const es = seguirTrabajo(
        id,
        (trabajo) => {
          callbacks.current.onCambio(trabajo);
          if (!estaActivo(trabajo)) {
            abiertos.current.delete(id);
            callbacks.current.onTermino(trabajo);
          }
        },
        () => {
          abiertos.current.delete(id);
          callbacks.current.onCorte();
        }
      );
      abiertos.current.set(id, es);
    }

    for (const [id, es] of abiertos.current) {
      if (!activos.has(id)) {
        es.close();
        abiertos.current.delete(id);
      }
    }
  }, [idsActivos, generacion]);

  useEffect(() => {
    const mapa = abiertos.current;
    return () => {
      for (const es of mapa.values()) es.close();
      mapa.clear();
    };
  }, []);
}
