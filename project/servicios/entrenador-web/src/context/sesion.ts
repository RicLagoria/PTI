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
