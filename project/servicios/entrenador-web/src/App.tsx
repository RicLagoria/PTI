// src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { HeroUIProvider } from "@heroui/react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import Layout from "./components/Layout/Layout";
import Aportes from "./components/Aportes/Aportes";
import Entrenamientos from "./components/Entrenamientos/Entrenamientos";
import Modelos from "./components/Modelos/Modelos";
import DetalleModelo from "./components/Modelos/DetalleModelo";
import LoginPage from "./components/login/LoginPage";
import { ProveedorSesion } from "./context/SesionContext";
import { useSesion } from "./context/sesion";

/**
 * Sin sesión no se monta ninguna pantalla del entrenador: no es solo para
 * esconderlas, es que todas arrancan pidiéndole algo a la API y sin token todo
 * responde 401. La API igual exige el token por su cuenta (api/auth.py), así
 * que esto es comodidad y no la cerradura.
 */
function Contenido() {
  const { perfil } = useSesion();
  if (!perfil) return <LoginPage />;

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Aportes />} />
        <Route path="entrenamientos" element={<Entrenamientos />} />
        <Route path="modelos" element={<Modelos />} />
        <Route path="modelos/:version" element={<DetalleModelo />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <NextThemesProvider attribute="class" enableSystem defaultTheme="dark">
        <HeroUIProvider>
          <ProveedorSesion>
            <Contenido />
          </ProveedorSesion>
        </HeroUIProvider>
      </NextThemesProvider>
    </BrowserRouter>
  );
}
