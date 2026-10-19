// =====================================
// src/context/AppContext.tsx
// =====================================
import React, { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import {
  cerrarSesion as cerrarSesionServicio,
  obtenerPerfilGuardado,
  obtenerToken,
  type Perfil,
} from "../services/AuthService";

interface AppContextType {
  isLoggedIn: boolean;
  perfil: Perfil | null;
  iniciarSesion: (perfil: Perfil) => void;
  cerrarSesion: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
};

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [perfil, setPerfil] = useState<Perfil | null>(() => {
    // Si hay token guardado pero no perfil (o viceversa), mejor arrancar
    // deslogueado que mostrar datos a medias.
    return obtenerToken() ? obtenerPerfilGuardado() : null;
  });

  const iniciarSesion = (nuevoPerfil: Perfil) => {
    setPerfil(nuevoPerfil);
  };

  const cerrarSesion = () => {
    cerrarSesionServicio();
    setPerfil(null);
  };

  const value: AppContextType = {
    isLoggedIn: perfil !== null,
    perfil,
    iniciarSesion,
    cerrarSesion,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
