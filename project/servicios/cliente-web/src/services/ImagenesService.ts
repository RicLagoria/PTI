// =====================================
// src/services/ImagenesService.ts
// =====================================
import ApiConfig from "../config/apiConfig";
import { conTokenEnUrl, headerAuth } from "./AuthService";

export interface ImagenMeta {
  id: string;
  nombre: string;
  usuario_nombre: string | null;
  fecha_subida: string;
  ancho_px: number;
  alto_px: number;
  bounds: [[number, number], [number, number]]; // [[sur, oeste], [norte, este]]
  minzoom: number;
  maxzoom: number;
}

export interface Deteccion {
  fila: number;
  col: number;
  clase: string;
  confianza: number;
  box_local?: number[];
  box_global_px: number[];
  gps_centro: { lat: number; lon: number };
}

export interface ChunkAnalisis {
  analisis_id: number;
  bloque: number;
  total_bloques: number;
  progreso_pct: number;
  activas: number;
  detecciones: Deteccion[];
  total_acumuladas: number;
}

export interface AnalisisHistorial {
  id: number;
  version_modelo: string;
  conf_umbral: number;
  cuadrante: number | null;
  fecha_inicio: string;
  fecha_fin: string | null;
  total_celdas: number;
  celdas_activas: number | null;
  estado: "en_progreso" | "completo" | "error";
  usuario_nombre: string | null;
  total_detecciones: number;
}

export interface AnalisisDetalle extends AnalisisHistorial {
  ortomosaico_id: string;
  detecciones: Deteccion[];
}

async function manejarError(res: Response, mensajeDefault: string): Promise<never> {
  let detalle = mensajeDefault;
  try {
    const data = await res.json();
    if (data?.detail) detalle = data.detail;
  } catch {
    // sin body JSON, nos quedamos con el mensaje default
  }
  throw new Error(detalle);
}

export async function listarImagenes(): Promise<ImagenMeta[]> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, "No se pudo obtener la lista de ortomosaicos.");
  return res.json();
}

export async function obtenerMetadata(id: string): Promise<ImagenMeta> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes/${id}/metadata`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, "No se pudo obtener los metadatos del ortomosaico.");
  return res.json();
}

export function urlTeselas(id: string): string {
  // Leaflet pide esto como <img src>, no puede mandar headers: el token va en la URL.
  return conTokenEnUrl(`${ApiConfig.baseURL}/imagenes/${id}/tiles/{z}/{x}/{y}.png`);
}

export function subirImagen(archivo: File, onProgreso: (pct: number) => void): Promise<ImagenMeta> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${ApiConfig.baseURL}/imagenes?nombre=${encodeURIComponent(archivo.name)}`);
    const auth = headerAuth().Authorization;
    if (auth) xhr.setRequestHeader("Authorization", auth);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgreso(Math.round((e.loaded / e.total) * 100));
    };

    xhr.onload = () => {
      let data: any = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        reject(new Error("Respuesta inválida del servidor."));
        return;
      }
      if (xhr.status === 201) resolve(data as ImagenMeta);
      else reject(new Error(data.detail || "No se pudo subir la imagen."));
    };

    xhr.onerror = () => reject(new Error("Se perdió la conexión con el servidor."));
    xhr.send(archivo);
  });
}

export interface OpcionesAnalisis {
  cuadrante?: number;
  conf?: number;
}

/**
 * Abre un stream SSE contra /analizar-stream. Devuelve el EventSource para
 * que el caller pueda cerrarlo (por ejemplo, al desmontar el componente).
 */
export function analizarEnVivo(
  id: string,
  opciones: OpcionesAnalisis,
  onChunk: (chunk: ChunkAnalisis) => void,
  onFin: () => void,
  onError: () => void
): EventSource {
  const params = new URLSearchParams();
  if (opciones.cuadrante) params.set("cuadrante", String(opciones.cuadrante));
  params.set("conf", String(opciones.conf ?? 0.1));

  // EventSource tampoco puede mandar headers custom: mismo truco del token en la URL.
  const url = conTokenEnUrl(`${ApiConfig.baseURL}/imagenes/${id}/analizar-stream?${params.toString()}`);
  const es = new EventSource(url);

  es.onmessage = (event) => {
    const chunk: ChunkAnalisis = JSON.parse(event.data);
    onChunk(chunk);
    if (chunk.bloque >= chunk.total_bloques) {
      es.close();
      onFin();
    }
  };

  es.onerror = () => {
    es.close();
    onError();
  };

  return es;
}

// =====================================
// Historial de análisis (ya no se pisan entre sí: cada corrida queda
// guardada en Postgres, ver datos.py del lado del servidor).
// =====================================

export async function listarHistorialAnalisis(imagenId: string): Promise<AnalisisHistorial[]> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, "No se pudo obtener el historial de análisis.");
  return res.json();
}

export async function obtenerAnalisisPasado(imagenId: string, analisisId: number): Promise<AnalisisDetalle> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis/${analisisId}`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, "No se pudo obtener ese análisis.");
  return res.json();
}

/** Son <a href download>, no fetch: el token viaja en la URL igual que en teselas/SSE. */
export function urlExportarGeoJSON(imagenId: string, analisisId: number): string {
  return conTokenEnUrl(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis/${analisisId}/exportar.geojson`);
}

export function urlExportarCSV(imagenId: string, analisisId: number): string {
  return conTokenEnUrl(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis/${analisisId}/exportar.csv`);
}

/** El informe visual: la imagen del campo con las detecciones marcadas, no solo datos. */
export function urlExportarPDF(imagenId: string, analisisId: number): string {
  return conTokenEnUrl(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis/${analisisId}/exportar.pdf`);
}

// Para la vista previa en el drawer (fetch con header, no <a href>): traen el
// contenido ya mismo en vez de solo la URL de descarga.

export async function obtenerTextoExportado(imagenId: string, analisisId: number, formato: "geojson" | "csv"): Promise<string> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis/${analisisId}/exportar.${formato}`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, `No se pudo obtener el ${formato.toUpperCase()}.`);
  return res.text();
}

export async function obtenerPdfBlob(imagenId: string, analisisId: number): Promise<Blob> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes/${imagenId}/analisis/${analisisId}/exportar.pdf`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, "No se pudo generar el PDF.");
  return res.blob();
}
