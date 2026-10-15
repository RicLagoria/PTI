// =====================================
// src/services/ImagenesService.ts
// =====================================
import ApiConfig from "../config/apiConfig";

export interface ImagenMeta {
  id: string;
  nombre: string;
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
  box_local: number[];
  box_global_px: number[];
  gps_centro: { lat: number; lon: number };
}

export interface ChunkAnalisis {
  bloque: number;
  total_bloques: number;
  progreso_pct: number;
  activas: number;
  detecciones: Deteccion[];
  total_acumuladas: number;
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
  const res = await fetch(`${ApiConfig.baseURL}/imagenes`);
  if (!res.ok) return manejarError(res, "No se pudo obtener la lista de ortomosaicos.");
  return res.json();
}

export async function obtenerMetadata(id: string): Promise<ImagenMeta> {
  const res = await fetch(`${ApiConfig.baseURL}/imagenes/${id}/metadata`);
  if (!res.ok) return manejarError(res, "No se pudo obtener los metadatos del ortomosaico.");
  return res.json();
}

export function urlTeselas(id: string): string {
  return `${ApiConfig.baseURL}/imagenes/${id}/tiles/{z}/{x}/{y}.png`;
}

export function subirImagen(archivo: File, onProgreso: (pct: number) => void): Promise<ImagenMeta> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${ApiConfig.baseURL}/imagenes?nombre=${encodeURIComponent(archivo.name)}`);

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

  const es = new EventSource(`${ApiConfig.baseURL}/imagenes/${id}/analizar-stream?${params.toString()}`);

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
