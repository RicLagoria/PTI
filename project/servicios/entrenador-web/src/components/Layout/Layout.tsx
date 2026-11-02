// =====================================
// src/components/Layout/Layout.tsx
// =====================================
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Chip,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from "@heroui/react";
import { motion } from "framer-motion";
import { useTheme } from "next-themes";
import { BrainCircuit, ChevronDown, FolderUp, Leaf, LogOut, Moon, Sun, Boxes, UserCircle2 } from "lucide-react";
import { useSesion } from "../../context/sesion";

const tabs = [
  {
    path: "/",
    label: "Aportes",
    icon: FolderUp,
    descripcion: "Subí imágenes etiquetadas con labelme. Cada aporte se valida contra la lista canónica de clases antes de guardarse.",
  },
  {
    path: "/entrenamientos",
    label: "Entrenamientos",
    icon: BrainCircuit,
    descripcion: "Elegí qué aportes usar y lanzá un entrenamiento. Se atienden en el orden en que se encolaron; si hay varios workers, corren varios a la vez.",
  },
  {
    path: "/modelos",
    label: "Modelos",
    icon: Boxes,
    descripcion: "Cada entrenamiento publica una versión nueva. Compará sus métricas y activá la que van a usar los análisis.",
  },
];

export default function Layout() {
  const location = useLocation();
  const { resolvedTheme, setTheme } = useTheme();
  const { perfil, cerrarSesion } = useSesion();
  // /modelos/v_123 cuenta como el tab Modelos
  const tabActiva =
    tabs.find((tab) => tab.path === location.pathname || (tab.path !== "/" && location.pathname.startsWith(`${tab.path}/`))) ?? tabs[0];
  const oscuro = resolvedTheme === "dark";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      <Navbar maxWidth="xl" className="bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <NavbarContent>
          <NavbarBrand className="gap-2">
            <Leaf className="h-6 w-6 text-emerald-600" />
            <span className="font-bold">AgroVision</span>
            {/* En un celular no entra junto a los tabs y empuja el botón de tema fuera de la pantalla */}
            <Chip size="sm" variant="flat" color="success" className="hidden sm:flex">
              Entrenador
            </Chip>
          </NavbarBrand>
        </NavbarContent>

        <NavbarContent justify="end" className="gap-1 sm:gap-2">
          {tabs.map((tab) => {
            const Icono = tab.icon;
            const activa = tab.path === tabActiva.path;
            return (
              <NavbarItem key={tab.path}>
                {/* Link plano y no Button de HeroUI, por el mismo motivo que en cliente-web:
                    el Button usado como Link se queda con el aro de presión pegado al navegar. */}
                <Link
                  to={tab.path}
                  aria-label={tab.label}
                  className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors ${
                    activa
                      ? "bg-blue-600 text-white dark:bg-blue-700"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  }`}
                >
                  <Icono className="h-4 w-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </Link>
              </NavbarItem>
            );
          })}
          <NavbarItem>
            <button
              type="button"
              onClick={() => setTheme(oscuro ? "light" : "dark")}
              aria-label={oscuro ? "Usar tema claro" : "Usar tema oscuro"}
              className="rounded-xl p-2 text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              {oscuro ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </NavbarItem>

          {/* Quién sos + cerrar sesión en un solo menú, igual que en cliente-web:
              la navbar ya tiene tres tabs y el botón de tema, y dos controles
              sueltos más no entran en un celular. */}
          {perfil && (
            <NavbarItem>
              <Dropdown placement="bottom-end">
                <DropdownTrigger>
                  <button
                    type="button"
                    className="flex items-center gap-2 rounded-xl py-1 pl-1 pr-2 transition-colors hover:bg-slate-100 dark:hover:bg-slate-700"
                  >
                    {perfil.avatar_url ? (
                      <img
                        src={perfil.avatar_url}
                        alt={perfil.nombre_completo}
                        className="h-8 w-8 rounded-full border border-slate-200 object-cover dark:border-slate-600"
                      />
                    ) : (
                      <UserCircle2 className="h-8 w-8 text-slate-400" />
                    )}
                    <span className="hidden text-sm font-semibold lg:inline">{perfil.nombre_completo}</span>
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  </button>
                </DropdownTrigger>
                <DropdownMenu aria-label="Menú de usuario">
                  <DropdownItem key="rol" isReadOnly textValue="rol" description={`@${perfil.username}`} className="cursor-default">
                    <span className="font-semibold capitalize">{perfil.rol}</span>
                  </DropdownItem>
                  <DropdownItem
                    key="salir"
                    color="danger"
                    className="text-danger"
                    startContent={<LogOut className="h-4 w-4" />}
                    onPress={cerrarSesion}
                  >
                    Cerrar sesión
                  </DropdownItem>
                </DropdownMenu>
              </Dropdown>
            </NavbarItem>
          )}
        </NavbarContent>
      </Navbar>

      <main className="mx-auto max-w-7xl p-4 sm:p-6">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
          className="space-y-6"
        >
          <div>
            <h1 className="text-3xl font-bold">{tabActiva.label}</h1>
            <p className="mt-1 max-w-3xl text-slate-600 dark:text-slate-400">{tabActiva.descripcion}</p>
          </div>
          <Outlet />
        </motion.div>
      </main>
    </div>
  );
}
