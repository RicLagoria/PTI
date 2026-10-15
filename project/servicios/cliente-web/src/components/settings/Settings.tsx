import { useEffect, useState } from "react";
import { Card, CardBody, Button, Chip } from "@heroui/react";
import { useTheme } from "next-themes";

export default function Settings() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const currentTheme = theme === "system" ? resolvedTheme : theme;
  const themeLabel = currentTheme === "dark" ? "Oscuro" : "Claro";

  if (!mounted) {
    return null;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Configuración</h1>
          <p className="text-slate-600 dark:text-slate-400">Controla el tema de la aplicación y ajusta opciones de visualización.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip color="secondary" className="dark:bg-slate-600 dark:text-slate-200">Tema</Chip>
          <Chip color="secondary" className="dark:bg-slate-600 dark:text-slate-200">Preferencias</Chip>
        </div>
      </div>

      <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <CardBody className="space-y-6">
          <div className="space-y-2">
            <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Tema de la aplicación</p>
            <h2 className="text-2xl font-semibold">Modo de color</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-[1.3fr_0.7fr] items-center">
            <div className="rounded-3xl bg-slate-50 p-6 dark:bg-slate-700">
              <p className="text-slate-600 dark:text-slate-400">Tema actual:</p>
              <p className="mt-2 text-3xl font-semibold">{themeLabel}</p>
            </div>
            <Button
              color="primary"
              size="lg"
              onClick={() => setTheme(currentTheme === "dark" ? "light" : "dark")}
              className="dark:bg-blue-700 dark:text-blue-100 dark:hover:bg-blue-600"
            >
              Cambiar a {currentTheme === "dark" ? "Claro" : "Oscuro"}
            </Button>
          </div>

          <p className="text-sm text-slate-500 dark:text-slate-400">
            El tema se guardará en tu navegador. Podés volver al dashboard y ver cómo cambia el estilo en toda la app.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
