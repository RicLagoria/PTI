// =====================================
// src/services/EntrenamientoService.ts
// =====================================
// Cliente de ia-entrenamiento-api (contratos/ia-entrenamiento.openapi.yaml).
import ApiConfig from "../config/apiConfig";

export interface Dataset {
  id: string;
  nombre: string;
  archivo_original: string;
  fecha_creacion: string;
  clases: string[];
  total_imagenes: number;
  total_anotaciones: number;
  anotaciones_por_clase: Record<string, number>;
  imagenes_sin_objetos: number;
  imagenes_sin_anotar: number;
  formas_ignoradas: number;
  cajas_descartadas: number;
}

export type EstadoTrabajo = "pendiente" | "ejecutando" | "completado" | "fallido";

export interface Metricas {
  // Durante el entrenamiento: la época que acaba de cerrar
  epoca?: number;
  total_epocas?: number;
  perdida?: number;
  // Al publicar: la mejor época (la que quedó como best.pt)
  epoca_mejor?: number;
  epocas_entrenadas?: number;
  precision?: number;
  recall?: number;
  map50?: number;
  map50_95?: number;
  /** El entrenamiento terminó y el worker está evaluando best.pt */
  evaluando?: boolean;
}

export interface Trabajo {
  id: string;
  estado: EstadoTrabajo;
  fecha_creacion: string;
  datasets: string[];
  epocas: number;
  imgsz: number;
  pesos_base: string;
  fraccion_validacion?: number;
  progreso_epocas: number;
  metricas: Metricas;
  version_generada: string | null;
  error: string | null;
  /** Réplica del worker que lo reclamó (hostname-pid); falta mientras está en cola */
  worker?: string;
}

export interface Modelo {
  version: string;
  activo: boolean;
  tamano_mb: number;
  meta: {
    version?: string;
    fecha_creacion?: string;
    origen?: "semilla" | "entrenamiento";
    trabajo_id?: string;
    datasets?: string[];
    epocas?: number;
    imgsz?: number;
    pesos_base?: string;
    clases?: string[];
    imagenes_train?: number;
    imagenes_val?: number;
    fraccion_validacion?: number;
    error_evaluacion?: string | null;
    metricas?: Metricas;
  };
}

export interface MetricasPorClase {
  clase: string;
  instancias: number;
  precision: number | null;
  recall: number | null;
  map50: number | null;
  map50_95: number | null;
}

/** Evaluación de best.pt sobre las imágenes de validación del entrenamiento (evaluacion.json). */
export interface Evaluacion {
  conjunto: string;
  metricas: { precision: number; recall: number; map50: number; map50_95: number };
  umbral_recomendado: number | null;
  por_clase: MetricasPorClase[];
  matriz_confusion: {
    umbral: number;
    iou: number;
    /** Las clases y al final "fondo" */
    etiquetas: string[];
    /** filas_reales[real][predicho] = cantidad de cajas */
    filas_reales: number[][];
  };
  curvas_confianza: { confianza: number[]; precision: number[]; recall: number[]; f1: number[] } | null;
}

export interface EpocaHistorial {
  epoca: number;
  perdida_train: number | null;
  perdida_val: number | null;
  precision: number | null;
  recall: number | null;
  map50: number | null;
  map50_95: number | null;
}

export interface DetalleModelo {
  version: string;
  /** null en las versiones entrenadas fuera del sistema (la semilla) */
  evaluacion: Evaluacion | null;
  historial: EpocaHistorial[];
  /** Gráficos de Ultralytics disponibles en urlImagenModelo() */
  imagenes: string[];
}

export interface SolicitudEntrenamiento {
  datasets: string[];
  epocas: number;
  imgsz: number;
  pesos_base: string;
  fraccion_validacion: number;
}

/** Pesos oficiales que acepta la API además de las versiones del registro. */
export const PESOS_BASE_OFICIALES = ["yolov8n.pt"];

/**
 * Error de la API con el detalle que manda cuando rechaza un aporte o un
 * pedido: qué etiquetas no conoce, qué archivos fallaron, etc.
 */
export class ErrorApi extends Error {
  clasesDesconocidas?: Record<string, number>;
  clasesValidas?: string[];
  errores?: string[];
  erroresOmitidos?: number;

  constructor(mensaje: string, extra: Partial<ErrorApi> = {}) {
    super(mensaje);
    Object.assign(this, extra);
  }
}

/** Traduce cualquier forma de error de FastAPI (string, objeto propio o lista de validación) a ErrorApi. */
function errorDesdeRespuesta(cuerpo: unknown, mensajeDefault: string): ErrorApi {
  const detalle = (cuerpo as { detail?: unknown } | null)?.detail;
  if (typeof detalle === "string") return new ErrorApi(detalle);
  if (Array.isArray(detalle)) {
    // 422 de validación de FastAPI: [{loc, msg}, ...]
    const textos = detalle.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`);
    return new ErrorApi("El pedido tiene valores inválidos.", { errores: textos });
  }
  if (detalle && typeof detalle === "object") {
    const d = detalle as Record<string, unknown>;
    return new ErrorApi(String(d.mensaje ?? mensajeDefault), {
      clasesDesconocidas: d.clases_desconocidas as Record<string, number> | undefined,
      clasesValidas: d.clases_validas as string[] | undefined,
      errores: (d.errores as string[] | undefined) ??
        (d.datasets_inexistentes ? [`Datasets inexistentes: ${(d.datasets_inexistentes as string[]).join(", ")}`] : undefined) ??
        (d.pesos_base_validos ? [`Valores válidos: ${(d.pesos_base_validos as string[]).join(", ")}`] : undefined),
      erroresOmitidos: d.errores_omitidos as number | undefined,
    });
  }
  return new ErrorApi(mensajeDefault);
}

async function pedir<T>(ruta: string, mensajeDefault: string, opciones?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${ApiConfig.baseURL}${ruta}`, opciones);
  } catch {
    throw new ErrorApi("No hay conexión con ia-entrenamiento-api.");
  }
  if (!res.ok) {
    let cuerpo: unknown = null;
    try {
      cuerpo = await res.json();
    } catch {
      // sin body JSON, nos quedamos con el mensaje default
    }
    throw errorDesdeRespuesta(cuerpo, mensajeDefault);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const listarClases = () => pedir<string[]>("/clases", "No se pudo obtener la lista de clases.");

export const listarDatasets = () => pedir<Dataset[]>("/datasets", "No se pudo obtener la lista de aportes.");

export const eliminarDataset = (id: string) =>
  pedir<void>(`/datasets/${id}`, "No se pudo eliminar el aporte.", { method: "DELETE" });

export const listarTrabajos = () => pedir<Trabajo[]>("/entrenamientos", "No se pudo obtener la lista de entrenamientos.");

export const encolarEntrenamiento = (solicitud: SolicitudEntrenamiento) =>
  pedir<Trabajo>("/entrenamientos", "No se pudo encolar el entrenamiento.", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(solicitud),
  });

export const listarModelos = () => pedir<Modelo[]>("/modelos", "No se pudo obtener el registro de modelos.");

export const activarModelo = (version: string) =>
  pedir<{ mensaje: string }>(`/modelos/${encodeURIComponent(version)}/activar`, "No se pudo activar el modelo.", {
    method: "POST",
  });

export const obtenerDetalleModelo = (version: string) =>
  pedir<DetalleModelo>(`/modelos/${encodeURIComponent(version)}/detalle`, "No se pudo obtener la evaluación del modelo.");

export const urlImagenModelo = (version: string, nombre: string) =>
  `${ApiConfig.baseURL}/modelos/${encodeURIComponent(version)}/imagenes/${encodeURIComponent(nombre)}`;

/**
 * Cuántas imágenes de un aporte van a validación. Misma cuenta que
 * ensamblado.cantidad_validacion() en ia-entrenamiento: .5 se redondea hacia
 * arriba, al menos 1 de cada lado, y un aporte de una sola imagen va entero a
 * entrenamiento.
 */
export function cantidadValidacion(total: number, fraccion: number): number {
  if (total < 2) return 0;
  return Math.min(total - 1, Math.max(1, Math.floor(total * fraccion + 0.5)));
}

/**
 * Sube un ZIP de labelme. Usa XMLHttpRequest y no fetch para poder mostrar el
 * avance de la subida. Cuando llega al 100% la API todavía tiene que convertir
 * las anotaciones: `onSubido` avisa ese momento.
 */
export function subirDataset(
  archivo: File,
  nombre: string,
  onProgreso: (pct: number) => void,
  onSubido: () => void
): Promise<Dataset> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${ApiConfig.baseURL}/datasets`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgreso(Math.round((e.loaded / e.total) * 100));
    };
    xhr.upload.onload = onSubido;

    xhr.onload = () => {
      let cuerpo: unknown = null;
      try {
        cuerpo = JSON.parse(xhr.responseText);
      } catch {
        // respuesta sin JSON (por ejemplo, un 502 de nginx)
      }
      if (xhr.status === 201) resolve(cuerpo as Dataset);
      else reject(errorDesdeRespuesta(cuerpo, `La API respondió ${xhr.status} al subir el aporte.`));
    };
    xhr.onerror = () => reject(new ErrorApi("Se perdió la conexión con el servidor."));

    const formulario = new FormData();
    formulario.append("archivo", archivo);
    if (nombre.trim()) formulario.append("nombre", nombre.trim());
    xhr.send(formulario);
  });
}

/**
 * Sigue un entrenamiento por SSE. La API manda el trabajo completo cada 2 s y
 * corta el stream al terminar; hay que cerrar el EventSource en ese momento
 * porque si no el navegador reconecta solo y vuelve a pedir el stream.
 */
export function seguirTrabajo(
  id: string,
  onCambio: (trabajo: Trabajo) => void,
  onCorte: () => void
): EventSource {
  const es = new EventSource(`${ApiConfig.baseURL}/entrenamientos/${id}/stream`);
  es.onmessage = (event) => {
    const trabajo: Trabajo = JSON.parse(event.data);
    onCambio(trabajo);
    if (trabajo.estado === "completado" || trabajo.estado === "fallido") es.close();
  };
  es.onerror = () => {
    es.close();
    onCorte();
  };
  return es;
}
