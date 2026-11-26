// =====================================
// src/context/sesion.ts
// =====================================
// El contexto y su hook viven acá y no en SesionContext.tsx porque el plugin de
// Fast Refresh exige que un archivo de componentes exporte solo componentes.
import { createContext, useContext } from "react";
import type { Perfil } from "../services/AuthService";

export interface Sesion {
  perfil: Perfil | null;
  /** Qué mostrar arriba del login cuando la sesión se cayó sola. */
  aviso: string | null;
  iniciarSesion: (perfil: Perfil) => void;
  cerrarSesion: () => void;
}

export const SesionContext = createContext<Sesion | null>(null);

export function useSesion(): Sesion {
  const contexto = useContext(SesionContext);
  if (!contexto) throw new Error("useSesion se usó fuera de ProveedorSesion.");
  return contexto;
}

/**
 * Qué puede hacer el usuario según su rol (el mismo criterio que la API):
 *   lector       solo mira aportes, entrenamientos y modelos
 *   colaborador  además sube aportes, deriva escalas y encola/cancela entrenamientos
 *   admin        además borra aportes y activa modelos
 * Es solo para no mostrar botones que la API va a rechazar con 403.
 */
export function usePermisos() {
  const { perfil } = useSesion();
  const rol = perfil?.rol;
  return {
    puedeAportar: rol === "colaborador" || rol === "admin",
    esAdmin: rol === "admin",
  };
}
