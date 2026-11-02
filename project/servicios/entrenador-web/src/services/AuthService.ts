// =====================================
// src/services/AuthService.ts
// =====================================
// Las cuentas son las mismas que las del sitio de análisis: quien valida
// usuario y contraseña es cliente-api, no ia-entrenamiento-api. El nginx de
// este front (y el proxy de vite en "npm run dev") reenvía /auth a cliente-api,
// así desde el navegador es el mismo origen y no hay CORS de por medio.
//
// ia-entrenamiento-api solo verifica la firma del token con el mismo JWT_SECRET
// (ver su api/auth.py), así que el plano IA no conoce las cuentas ni la base.
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

/**
 * Se dispara cuando la API rechaza el token (expiró, o los dos planos tienen
 * JWT_SECRET distinto). El contexto lo escucha para volver al login en vez de
 * dejar la pantalla con un error de "no se pudo obtener la lista". Es un evento
 * y no un callback para que el servicio no tenga que conocer a React.
 */
export const EVENTO_SESION_CAIDA = "agrovision:sesion-caida";

export async function iniciarSesion(usuario: string, contrasena: string): Promise<Perfil> {
  let res: Response;
  try {
    res = await fetch(`${ApiConfig.authURL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, contrasena }),
    });
  } catch {
    throw new Error("No hay conexión con cliente-api, que es quien valida las cuentas.");
  }
  if (!res.ok) {
    let detalle = "Usuario o contraseña incorrectos.";
    try {
      const data = await res.json();
      if (data?.detail) detalle = data.detail;
    } catch {
      // sin body JSON, nos quedamos con el mensaje default
    }
    throw new Error(detalle);
  }

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
 * Para los dos casos que no pueden mandar headers: el progreso del
 * entrenamiento, que es un EventSource, y los gráficos de cada modelo, que son
 * <img src>. El token va como query param; la API acepta las dos formas.
 */
export function conTokenEnUrl(url: string): string {
  const token = obtenerToken();
  if (!token) return url;
  const separador = url.includes("?") ? "&" : "?";
  return `${url}${separador}token=${encodeURIComponent(token)}`;
}

/** Borra la sesión y avisa al contexto. La llama el cliente de la API ante un 401. */
export function sesionCaida(): void {
  cerrarSesion();
  window.dispatchEvent(new Event(EVENTO_SESION_CAIDA));
}
