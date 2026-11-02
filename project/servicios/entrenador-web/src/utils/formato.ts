// Formatos compartidos por las pantallas

export function fecha(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { dateStyle: "medium", timeStyle: "short" });
}

/** Las métricas de YOLO van de 0 a 1; se muestran como porcentaje. */
export function porcentaje(valor?: number): string {
  if (valor === undefined || valor === null) return "—";
  return `${(valor * 100).toLocaleString("es-AR", { maximumFractionDigits: 1 })} %`;
}

export function numero(valor?: number, decimales = 0): string {
  if (valor === undefined || valor === null) return "—";
  return valor.toLocaleString("es-AR", { maximumFractionDigits: decimales });
}

/** 45 s · 6 min 20 s · 25 min · 1 h 05 min */
export function duracion(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const minutos = Math.floor(s / 60);
  if (minutos < 10) return `${minutos} min ${String(s % 60).padStart(2, "0")} s`;
  if (minutos < 60) return `${minutos} min`;
  return `${Math.floor(minutos / 60)} h ${String(minutos % 60).padStart(2, "0")} min`;
}

/** Hora local en la que termina algo que dura `segundos` desde ahora. */
export function horaDentroDe(segundos: number): string {
  return new Date(Date.now() + segundos * 1000).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

export function tamanoArchivo(bytes: number): string {
  if (bytes < 1024 * 1024) return `${numero(bytes / 1024, 0)} KB`;
  return `${numero(bytes / (1024 * 1024), 1)} MB`;
}

export function plural(cantidad: number, singular: string, pluralTexto = `${singular}s`): string {
  return `${numero(cantidad)} ${cantidad === 1 ? singular : pluralTexto}`;
}
