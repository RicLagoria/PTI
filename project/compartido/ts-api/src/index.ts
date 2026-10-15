// Taxonomía canónica
export type ClaseCanonica = "maleza" | "falla" | "camino" | "lodazal" | string;

// Contrato ia-inferencia
export interface InfoModelo {
  version: string;
  clases: ClaseCanonica[];
  imgsz: number;
  metricas?: Record<string, unknown>;
  disponible?: boolean;
}

export interface DeteccionLocal {
  id: string;
  clase: string;
  confianza: number;
  box_local: [number, number, number, number];
}

export interface RespuestaInferencia {
  version_modelo: string;
  total_teselas: number;
  detecciones: DeteccionLocal[];
}

// Contrato cliente-api
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

export interface DeteccionGlobal {
  fila: number;
  col: number;
  clase: string;
  confianza: number;
  box_local: [number, number, number, number];
  box_global_px: [number, number, number, number];
  gps_centro: { lat: number; lon: number };
}

export interface ChunkAnalisis {
  bloque: number;
  total_bloques: number;
  progreso_pct: number;
  activas: number;
  detecciones: DeteccionGlobal[];
  total_acumuladas: number;
}

// Contrato ia-entrenamiento
export interface DatasetMeta {
  id: string;
  nombre: string;
  fecha_subida: string;
  total_imagenes: number;
  clases_canonicas: string[];
}

export interface TrabajoEntrenamiento {
  id: string;
  estado: "pendiente" | "ejecutando" | "completado" | "fallido";
  fecha_creacion: string;
  datasets: string[];
  epocas: number;
  imgsz: number;
  pesos_base: string;
  progreso_epocas: number;
  metricas: Record<string, unknown>;
  version_generada?: string | null;
  error?: string | null;
}

export interface ModeloMeta {
  version: string;
  activo: boolean;
  tamano_mb: number;
  meta: Record<string, unknown>;
}

