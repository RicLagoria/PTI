// =====================================
// src/components/login/LoginPage.tsx
// =====================================
import { useState } from "react";
import { Input, Button, Card, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter } from "@heroui/react";
import { Leaf, User, Lock } from "lucide-react";
import { motion } from "framer-motion";
import { useAppContext } from "../../context/AppContext";
import { iniciarSesion as iniciarSesionApi } from "../../services/AuthService";
import fieldImg from "../../assets/img/sale.jpg";

export default function LoginPage() {
  const [loginData, setLoginData] = useState({ username: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const { iniciarSesion } = useAppContext();

  const handleLogin = async () => {
    if (!loginData.username || !loginData.password) {
      setErrorMsg("Completá usuario y contraseña.");
      return;
    }
    setLoading(true);
    try {
      const perfil = await iniciarSesionApi(loginData.username, loginData.password);
      iniciarSesion(perfil);
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Usuario o contraseña incorrectos.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !loading) {
      handleLogin();
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-3">
      {/* Lado izquierdo */}
      <div className="hidden lg:flex relative col-span-2">
        <img src={fieldImg} className="absolute inset-0 w-full h-full object-cover filter blur-sm" />
        <div className="absolute inset-0 bg-black/30 flex items-center px-20">
          <div>
            <h2 className="text-5xl lg:text-6xl font-extrabold bg-clip-text bg-gradient-to-r from-emerald-300 to-green-500 flex items-center gap-3 drop-shadow-lg">
              <Leaf className="w-12 h-12" /> Detección de Malezas
            </h2>
            <p className="mt-4 text-lg lg:text-xl text-gray-100/90 leading-relaxed drop-shadow-md">
              Accede al panel de análisis de imágenes de campo para identificar zonas con malezas y posibles intervenciones.
            </p>
          </div>
        </div>
      </div>

      {/* Lado derecho */}
      <div className="flex items-center justify-center w-full px-6 py-12 lg:col-span-1">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 50 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="w-full max-w-md"
        >
          <Card
            className="p-8 shadow-2xl rounded-2xl"
            style={{
              background: "linear-gradient(135deg, #0f766e 0%, #16a34a 100%)",
            }}
          >
            <div className="text-center">
              <h2 className="text-3xl font-bold text-white">Iniciar Sesión</h2>
              <p className="mt-2 text-gray-200">Entrá con tu usuario de GitHub del equipo</p>
            </div>

            <div className="mt-8 flex flex-col gap-6">
              <Input
                label="Usuario"
                value={loginData.username}
                onChange={(e) => setLoginData({ ...loginData, username: e.target.value })}
                placeholder="tu-usuario-de-github"
                onKeyPress={handleKeyPress}
                startContent={<User className="w-5 h-5 text-white" />}
              />
              <Input
                label="Contraseña"
                type="password"
                value={loginData.password}
                onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                onKeyPress={handleKeyPress}
                startContent={<Lock className="w-5 h-5 text-white" />}
              />

              <motion.div whileTap={{ scale: loading ? 1 : 0.96 }}>
                <Button
                  color="primary"
                  size="lg"
                  className="w-full font-semibold"
                  onClick={handleLogin}
                  isLoading={loading}
                  disabled={loading}
                >
                  {loading ? "Validando..." : "Entrar al panel"}
                </Button>
              </motion.div>
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Modal de error */}
      <Modal isOpen={errorMsg !== null} onOpenChange={(open) => !open && setErrorMsg(null)}>
        <ModalContent>
          <ModalHeader className="font-bold text-red-500">Autenticación fallida</ModalHeader>
          <ModalBody>
            <p>{errorMsg}</p>
          </ModalBody>
          <ModalFooter>
            <Button color="danger" onClick={() => setErrorMsg(null)}>
              Cerrar
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
