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

export function tamanoArchivo(bytes: number): string {
  if (bytes < 1024 * 1024) return `${numero(bytes / 1024, 0)} KB`;
  return `${numero(bytes / (1024 * 1024), 1)} MB`;
}

export function plural(cantidad: number, singular: string, pluralTexto = `${singular}s`): string {
  return `${numero(cantidad)} ${cantidad === 1 ? singular : pluralTexto}`;
}
