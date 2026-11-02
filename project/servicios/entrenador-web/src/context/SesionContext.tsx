// =====================================
// src/context/SesionContext.tsx
// =====================================
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  EVENTO_SESION_CAIDA,
  cerrarSesion as borrarSesion,
  obtenerPerfilGuardado,
  obtenerToken,
} from "../services/AuthService";
import type { Perfil } from "../services/AuthService";
import { SesionContext } from "./sesion";

/**
 * El perfil arranca de localStorage, igual que en cliente-web: el token es un
 * JWT con el perfil adentro, así que no hace falta pedirle nada a la API para
 * saber quién está. Si el token está vencido, el primer pedido devuelve 401 y
 * el servicio dispara EVENTO_SESION_CAIDA, que nos trae de vuelta al login.
 */
export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [perfil, setPerfil] = useState<Perfil | null>(() =>
    obtenerToken() ? obtenerPerfilGuardado() : null
  );
  const [aviso, setAviso] = useState<string | null>(null);

  const iniciarSesion = useCallback((nuevo: Perfil) => {
    setAviso(null);
    setPerfil(nuevo);
  }, []);

  const cerrarSesion = useCallback(() => {
    borrarSesion();
    setAviso(null);
    setPerfil(null);
  }, []);

  useEffect(() => {
    const alCaer = () => {
      setPerfil(null);
      setAviso("La sesión expiró. Entrá de nuevo.");
    };
    window.addEventListener(EVENTO_SESION_CAIDA, alCaer);
    return () => window.removeEventListener(EVENTO_SESION_CAIDA, alCaer);
  }, []);

  const valor = useMemo(
    () => ({ perfil, aviso, iniciarSesion, cerrarSesion }),
    [perfil, aviso, iniciarSesion, cerrarSesion]
  );

  return <SesionContext.Provider value={valor}>{children}</SesionContext.Provider>;
}
