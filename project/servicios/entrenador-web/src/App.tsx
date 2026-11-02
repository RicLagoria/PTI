// src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { HeroUIProvider } from "@heroui/react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import Layout from "./components/Layout/Layout";
import Aportes from "./components/Aportes/Aportes";
import Entrenamientos from "./components/Entrenamientos/Entrenamientos";
import Modelos from "./components/Modelos/Modelos";
import DetalleModelo from "./components/Modelos/DetalleModelo";

export default function App() {
  return (
    <BrowserRouter>
      <NextThemesProvider attribute="class" enableSystem defaultTheme="dark">
        <HeroUIProvider>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Aportes />} />
              <Route path="entrenamientos" element={<Entrenamientos />} />
              <Route path="modelos" element={<Modelos />} />
              <Route path="modelos/:version" element={<DetalleModelo />} />
            </Route>
          </Routes>
        </HeroUIProvider>
      </NextThemesProvider>
    </BrowserRouter>
  );
}
