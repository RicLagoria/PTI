// src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./components/Home/Home";
import Dashboard from "./components/dashboard/Dashboard";
import FieldView from "./components/FieldView/FieldView";
import Settings from "./components/settings/Settings";
import { AppProvider } from "./context/AppContext";
import { HeroUIProvider } from "@heroui/react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <NextThemesProvider attribute="class" enableSystem defaultTheme="dark">
          <HeroUIProvider>
            <Routes>
              <Route path="/" element={<Home />}>
                <Route index element={<Dashboard />} />
                <Route path="campo" element={<FieldView />} />
                <Route path="settings" element={<Settings />} />
              </Route>
            </Routes>
          </HeroUIProvider>
        </NextThemesProvider>
      </BrowserRouter>
    </AppProvider>
  );
}
