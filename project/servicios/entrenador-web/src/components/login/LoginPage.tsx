// =====================================
// src/components/login/LoginPage.tsx
// =====================================
// Mismas cuentas que el sitio de análisis, pero sin la foto de campo del otro
// login: acá no hay nada que vender, el que entra viene a entrenar.
import { useState } from "react";
import { Button, Card, Chip, Input } from "@heroui/react";
import { AlertTriangle, Leaf, Lock, User } from "lucide-react";
import { motion } from "framer-motion";
import { useSesion } from "../../context/sesion";
import { iniciarSesion as iniciarSesionApi } from "../../services/AuthService";
import { claseTextoSuave } from "../comunes/estilos";

export default function LoginPage() {
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { aviso, iniciarSesion } = useSesion();

  const entrar = async () => {
    if (!usuario || !contrasena) {
      setError("Completá usuario y contraseña.");
      return;
    }
    setCargando(true);
    setError(null);
    try {
      iniciarSesion(await iniciarSesionApi(usuario, contrasena));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Usuario o contraseña incorrectos.");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28 }}
        className="w-full max-w-md"
      >
        <div className="mb-6 flex items-center justify-center gap-2">
          <Leaf className="h-7 w-7 text-emerald-600" />
          <span className="text-2xl font-bold">AgroVision</span>
          <Chip size="sm" variant="flat" color="success">
            Entrenador
          </Chip>
        </div>

        <Card className="border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h1 className="text-2xl font-bold">Iniciar sesión</h1>
          <p className={`mt-1 text-sm ${claseTextoSuave}`}>
            Entrá con la misma cuenta que usás en el sitio de análisis.
          </p>

          {(aviso ?? error) && (
            <p className="mt-4 flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {error ?? aviso}
            </p>
          )}

          {/* Un <form> y no un onKeyPress suelto: así el Enter manda desde
              cualquiera de los dos campos y el navegador puede ofrecer la
              contraseña guardada. */}
          <form
            className="mt-6 flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!cargando) entrar();
            }}
          >
            <Input
              label="Usuario"
              name="username"
              autoComplete="username"
              value={usuario}
              onValueChange={setUsuario}
              placeholder="tu-usuario-de-github"
              startContent={<User className="h-4 w-4 text-slate-400" />}
              isDisabled={cargando}
            />
            <Input
              label="Contraseña"
              name="password"
              type="password"
              autoComplete="current-password"
              value={contrasena}
              onValueChange={setContrasena}
              startContent={<Lock className="h-4 w-4 text-slate-400" />}
              isDisabled={cargando}
            />
            <Button type="submit" color="primary" size="lg" className="font-semibold" isLoading={cargando}>
              {cargando ? "Validando..." : "Entrar"}
            </Button>
          </form>
        </Card>

        <p className={`mt-4 text-center text-xs ${claseTextoSuave}`}>
          Las cuentas las administra el sitio de análisis; acá no se crean ni se cambian.
        </p>
      </motion.div>
    </div>
  );
}
