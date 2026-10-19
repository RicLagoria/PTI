import { useEffect, useState } from "react";
import { Card, CardBody, Button, Chip } from "@heroui/react";
import { useTheme } from "next-themes";
import { UserCircle2 } from "lucide-react";
import { useAppContext } from "../../context/AppContext";

function formatearFecha(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Settings() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { perfil } = useAppContext();
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
          <p className="text-slate-600 dark:text-slate-400">Tu perfil, el tema de la aplicación y otras preferencias.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip color="secondary" className="dark:bg-slate-600 dark:text-slate-200">Perfil</Chip>
          <Chip color="secondary" className="dark:bg-slate-600 dark:text-slate-200">Tema</Chip>
        </div>
      </div>

      {perfil && (
        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <CardBody className="space-y-6">
            <div className="flex items-center gap-4">
              {perfil.avatar_url ? (
                <img
                  src={perfil.avatar_url}
                  alt={perfil.nombre_completo}
                  className="h-16 w-16 rounded-full border border-slate-200 object-cover dark:border-slate-600"
                />
              ) : (
                <UserCircle2 className="h-16 w-16 text-slate-400" />
              )}
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Mi perfil</p>
                <h2 className="text-2xl font-semibold">{perfil.nombre_completo}</h2>
                <Chip
                  size="sm"
                  color={perfil.rol === "admin" ? "warning" : "secondary"}
                  className="mt-1 capitalize dark:bg-slate-600 dark:text-slate-200"
                >
                  {perfil.rol}
                </Chip>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-700">
                <p className="text-sm text-slate-500 dark:text-slate-400">Usuario</p>
                <p className="mt-1 text-lg font-semibold">{perfil.username}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-700">
                <p className="text-sm text-slate-500 dark:text-slate-400">Miembro desde</p>
                <p className="mt-1 text-lg font-semibold">{formatearFecha(perfil.fecha_alta)}</p>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-700">
                <p className="text-sm text-slate-500 dark:text-slate-400">Último acceso</p>
                <p className="mt-1 text-lg font-semibold">{formatearFecha(perfil.ultimo_acceso)}</p>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

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
