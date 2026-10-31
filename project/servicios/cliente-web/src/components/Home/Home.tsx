// =====================================
// src/components/Home/Home.tsx
// =====================================
import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
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
import { Leaf, Image, LayoutGrid, Settings2, UserCircle2, ChevronDown, User, LogOut } from "lucide-react";

import { useAppContext } from "../../context/AppContext";
import LoginPage from "../login/LoginPage";
import { obtenerEstadisticas } from "../../services/EstadisticasService";

const tabs = [
  { id: "/", label: "Dashboard", icon: LayoutGrid, path: "/" },
  { id: "/campo", label: "Imagen", icon: Image, path: "/campo" },
  { id: "/settings", label: "Ajustes", icon: Settings2, path: "/settings" },
];

export default function Home() {
  const { isLoggedIn, perfil, cerrarSesion } = useAppContext();
  const location = useLocation();
  const navegar = useNavigate();
  const [ultimoAnalisis, setUltimoAnalisis] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn) return;
    obtenerEstadisticas()
      .then((stats) => setUltimoAnalisis(stats.ultima_actualizacion))
      .catch(() => setUltimoAnalisis(null));
  }, [isLoggedIn]);

  if (!isLoggedIn || !perfil) return <LoginPage />;

  const activeTab = tabs.find((tab) => tab.path === location.pathname) || tabs[0];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      <Navbar className="bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <NavbarContent>
          <NavbarBrand>
            <Leaf className="w-6 h-6 text-emerald-600" />
            <span className="ml-2 font-bold">AgroVision</span>
          </NavbarBrand>
        </NavbarContent>

        <NavbarContent justify="end" className="gap-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = location.pathname === tab.path;
            return (
              <NavbarItem key={tab.id}>
                {/* Link de Tailwind plano a propósito: el Button de HeroUI usado
                    como Link se queda con el aro de foco/presión pegado cuando el
                    click dispara una navegación de react-router a mitad de gesto
                    (varios tabs quedan "presionados" al mismo tiempo). */}
                <Link
                  to={tab.path}
                  className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-blue-600 text-white dark:bg-blue-700"
                      : "bg-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </Link>
              </NavbarItem>
            );
          })}

          {/* Quién sos + cerrar sesión, unido en un solo menú: antes eran dos
              controles sueltos (nombre/rol + botón rojo) peleándose por el
              mismo espacio angosto de la navbar y se veían apretados. */}
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
                  <span className="hidden text-sm font-semibold sm:inline">{perfil.nombre_completo}</span>
                  <ChevronDown className="h-4 w-4 text-slate-400" />
                </button>
              </DropdownTrigger>
              <DropdownMenu aria-label="Menú de usuario">
                <DropdownItem key="rol" isReadOnly textValue="rol" description={`@${perfil.username}`} className="cursor-default">
                  <span className="font-semibold capitalize">{perfil.rol}</span>
                </DropdownItem>
                <DropdownItem key="perfil" onPress={() => navegar("/settings")} startContent={<User className="h-4 w-4" />}>
                  Ver mi perfil
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
        </NavbarContent>
      </Navbar>

      <div className="p-6">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
          className="space-y-8"
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-3xl font-bold capitalize">{activeTab.label}</h1>
              <p className="text-slate-600 dark:text-slate-400">
                Bienvenido {perfil.nombre_completo}
                {perfil.rol === "admin" && (
                  <Chip size="sm" color="warning" className="ml-2 align-middle dark:bg-amber-900 dark:text-amber-100">
                    admin
                  </Chip>
                )}
                . Navega entre el dashboard, la vista de imagen y las opciones de configuracion.
              </p>
            </div>
            <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3 shadow-sm dark:bg-slate-800 dark:border-slate-700">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Ultimo analisis</p>
              <p className="text-lg font-semibold">
                {ultimoAnalisis
                  ? new Date(ultimoAnalisis).toLocaleDateString("es-AR", { day: "2-digit", month: "long", year: "numeric" })
                  : "Sin análisis todavía"}
              </p>
            </div>
          </div>

          <Outlet />
        </motion.div>
      </div>
    </div>
  );
}
