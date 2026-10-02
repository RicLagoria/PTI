// =====================================
// src/components/Home/Home.tsx
// =====================================
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Button,
  Card,
  CardBody,
  Chip,
} from "@heroui/react";
import { motion } from "framer-motion";
import { Leaf, Image, LayoutGrid, Settings2 } from "lucide-react";

import { useAppContext } from "../../context/AppContext";
import LoginPage from "../login/LoginPage";

const tabs = [
  { id: "/", label: "Dashboard", icon: LayoutGrid, path: "/" },
  { id: "/campo", label: "Imagen", icon: Image, path: "/campo" },
  { id: "/settings", label: "Ajustes", icon: Settings2, path: "/settings" },
];

export default function Home() {
  const { isLoggedIn, setIsLoggedIn, username } = useAppContext();
  const location = useLocation();

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.setItem("isLoggedIn", "false");
    setIsLoggedIn(false);
  };

  if (!isLoggedIn) return <LoginPage />;

  const activeTab = tabs.find((tab) => tab.path === location.pathname) || tabs[0];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
      <Navbar className="bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <NavbarContent>
          <NavbarBrand>
            <Leaf className="w-6 h-6 text-emerald-600" />
            <span className="ml-2 font-bold">WeedVision</span>
          </NavbarBrand>
        </NavbarContent>

        <NavbarContent justify="end" className="gap-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = location.pathname === tab.path;
            return (
              <NavbarItem key={tab.id}>
                <Button
                  as={Link}
                  to={tab.path}
                  size="sm"
                  variant={isActive ? "solid" : "ghost"}
                  color={isActive ? "primary" : "secondary"}
                  className="capitalize dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
                >
                  <Icon className="mr-2 h-4 w-4" />
                  {tab.label}
                </Button>
              </NavbarItem>
            );
          })}
          <NavbarItem>
            <Button color="danger" variant="flat" onClick={handleLogout} className="dark:bg-red-900 dark:text-red-100 dark:hover:bg-red-800">
              Cerrar Sesion
            </Button>
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
                Bienvenido {username ?? "administrador"}. Navega entre el dashboard, la vista de imagen y las opciones de configuracion.
              </p>
            </div>
            <div className="rounded-2xl bg-white border border-slate-200 px-4 py-3 shadow-sm dark:bg-slate-800 dark:border-slate-700">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Ultimo analisis</p>
              <p className="text-lg font-semibold">07 de mayo, 2026</p>
            </div>
          </div>

          <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
            <CardBody className="grid gap-4 md:grid-cols-[260px_1fr] md:items-center">
              <div className="rounded-3xl bg-slate-50 p-4 dark:bg-slate-700">
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Usuario</p>
                <p className="mt-2 text-xl font-semibold">{username ?? "admin"}</p>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-slate-600 dark:text-slate-400">
                <span>Estas viendo la seccion:</span>
                <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
                  {activeTab.label}
                </Chip>
              </div>
            </CardBody>
          </Card>

          <Outlet />
        </motion.div>
      </div>
    </div>
  );
}

