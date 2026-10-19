// =====================================
// src/services/AuthService.ts
// =====================================
import ApiConfig from "../config/apiConfig";

export interface Perfil {
  username: string;
  nombre_completo: string;
  rol: string;
  avatar_url: string | null;
  fecha_alta: string | null;
  ultimo_acceso: string | null;
}

const CLAVE_TOKEN = "agrovision_token";
const CLAVE_PERFIL = "agrovision_perfil";

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

export async function iniciarSesion(usuario: string, contrasena: string): Promise<Perfil> {
  const res = await fetch(`${ApiConfig.baseURL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, contrasena }),
  });
  if (!res.ok) return manejarError(res, "Usuario o contraseña incorrectos.");

  const data = await res.json();
  localStorage.setItem(CLAVE_TOKEN, data.token);
  localStorage.setItem(CLAVE_PERFIL, JSON.stringify(data.perfil));
  return data.perfil as Perfil;
}

export function cerrarSesion(): void {
  localStorage.removeItem(CLAVE_TOKEN);
  localStorage.removeItem(CLAVE_PERFIL);
}

export function obtenerToken(): string | null {
  return localStorage.getItem(CLAVE_TOKEN);
}

export function obtenerPerfilGuardado(): Perfil | null {
  const crudo = localStorage.getItem(CLAVE_PERFIL);
  if (!crudo) return null;
  try {
    return JSON.parse(crudo) as Perfil;
  } catch {
    return null;
  }
}

/** Headers listos para pegarle a la API en cualquier fetch protegido. */
export function headerAuth(): Record<string, string> {
  const token = obtenerToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Para los dos casos que no pueden mandar headers custom (teselas de
 * Leaflet, que son <img>, y el streaming de análisis, que usa EventSource):
 * el token va como query param en vez de header. El backend acepta
 * cualquiera de los dos formas, ver auth.py del lado del servidor.
 */
export function conTokenEnUrl(url: string): string {
  const token = obtenerToken();
  if (!token) return url;
  const separador = url.includes("?") ? "&" : "?";
  return `${url}${separador}token=${encodeURIComponent(token)}`;
}
