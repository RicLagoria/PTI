// =====================================
// src/services/EstadisticasService.ts
// Los KPI reales del dashboard, calculados en SQL sobre ortomosaicos /
// analisis / detecciones (ver /estadisticas en cliente-api).
// =====================================
import ApiConfig from "../config/apiConfig";
import { headerAuth } from "./AuthService";

export interface DeteccionesPorClase {
  clase: string;
  cantidad: number;
}

export interface ModeloVersion {
  version_modelo: string;
  confianza_promedio: number;
  corridas: number;
  detecciones: number;
}

export interface EficienciaPunto {
  fecha: string;
  seg_por_celda: number;
}

export interface Estadisticas {
  total_ortomosaicos: number;
  total_analisis: number;
  ultima_actualizacion: string | null;
  cobertura: {
    clase_principal: string | null;
    pct_cobertura: number;
    detecciones_totales: number;
  };
  detecciones_por_clase: DeteccionesPorClase[];
  modelo: {
    por_version: ModeloVersion[];
  };
  eficiencia: {
    promedio_seg_por_celda: number | null;
    historial: EficienciaPunto[];
  };
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

export async function obtenerEstadisticas(): Promise<Estadisticas> {
  const res = await fetch(`${ApiConfig.baseURL}/estadisticas`, { headers: headerAuth() });
  if (!res.ok) return manejarError(res, "No se pudieron calcular las estadísticas.");
  return res.json();
}
