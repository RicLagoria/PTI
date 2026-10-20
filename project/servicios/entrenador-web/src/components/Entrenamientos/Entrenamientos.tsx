// =====================================
// src/components/Entrenamientos/Entrenamientos.tsx
// =====================================
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Card, CardBody, Checkbox, CheckboxGroup, Input, Select, SelectItem, Spinner } from "@heroui/react";
import type { SharedSelection } from "@heroui/react";
import { BrainCircuit, Clock } from "lucide-react";

import {
  cantidadValidacion,
  encolarEntrenamiento,
  listarDatasets,
  listarModelos,
  listarTrabajos,
  PESOS_BASE_OFICIALES,
  type Dataset,
  type Modelo,
  type Trabajo,
} from "../../services/EntrenamientoService";
import { estaActivo, useSeguimientoTrabajos } from "../../hooks/useSeguimientoTrabajos";
import { plural } from "../../utils/formato";
import PanelError from "../comunes/PanelError";
import { claseEtiqueta, claseTarjeta, claseTextoSuave } from "../comunes/estilos";
import TarjetaTrabajo from "./TarjetaTrabajo";

// La API acepta múltiplos de 32 entre 320 y 1280; estos son los razonables
const TAMANOS_IMAGEN = [320, 416, 512, 640, 800, 960, 1280];
// La API acepta entre 10% y 50% para validación
const FRACCIONES_VALIDACION = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5];
const ESPERA_TRAS_CORTE_MS = 5000;

/** Clave elegida en un Select de selección simple (vacía si se deseleccionó). */
const claveElegida = (claves: SharedSelection) => (claves === "all" ? "" : String(Array.from(claves)[0] ?? ""));

export default function Entrenamientos() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [modelos, setModelos] = useState<Modelo[]>([]);
  const [trabajos, setTrabajos] = useState<Trabajo[]>([]);
  const [generacion, setGeneracion] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<unknown>(null);

  const [elegidos, setElegidos] = useState<string[]>([]);
  const [epocas, setEpocas] = useState("50");
  const [imgsz, setImgsz] = useState("640");
  const [pesosBase, setPesosBase] = useState(PESOS_BASE_OFICIALES[0]);
  const [fraccion, setFraccion] = useState("0.25");
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState<unknown>(null);
  const reintento = useRef<number | undefined>(undefined);

  const recargar = useCallback(async () => {
    try {
      const [ds, ms, ts] = await Promise.all([listarDatasets(), listarModelos(), listarTrabajos()]);
      setDatasets([...ds].sort((a, b) => b.fecha_creacion.localeCompare(a.fecha_creacion)));
      setModelos(ms);
      setTrabajos(ts);
      setGeneracion((g) => g + 1);
      setErrorCarga(null);
    } catch (e) {
      setErrorCarga(e);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
    return () => window.clearTimeout(reintento.current);
  }, [recargar]);

  useSeguimientoTrabajos(
    trabajos,
    generacion,
    (actualizado) => setTrabajos((lista) => lista.map((t) => (t.id === actualizado.id ? actualizado : t))),
    // Un trabajo completado agrega una versión que se puede usar como pesos de partida
    () => recargar(),
    () => {
      window.clearTimeout(reintento.current);
      reintento.current = window.setTimeout(recargar, ESPERA_TRAS_CORTE_MS);
    }
  );

  const nombreDataset = (id: string) => datasets.find((d) => d.id === id)?.nombre ?? `${id} (eliminado)`;
  const aportesElegidos = datasets.filter((d) => elegidos.includes(d.id));
  const imagenesElegidas = aportesElegidos.reduce((s, d) => s + d.total_imagenes, 0);
  // Misma cuenta que el worker: el split se hace dentro de cada aporte
  const imagenesValidacion = aportesElegidos.reduce((s, d) => s + cantidadValidacion(d.total_imagenes, Number(fraccion)), 0);
  const epocasNumero = Number(epocas);
  const epocasValidas = Number.isInteger(epocasNumero) && epocasNumero >= 1 && epocasNumero <= 300;
  const puedeEnviar = elegidos.length > 0 && imagenesElegidas >= 2 && epocasValidas && !enviando;

  // Los workers reclaman primero el pendiente más viejo: la posición sale de ordenar
  // los pendientes por fecha. Los que ya están corriendo no cuentan, porque con
  // varios workers no necesariamente hay que esperarlos.
  const pendientes = trabajos.filter((t) => t.estado === "pendiente").sort((a, b) => a.fecha_creacion.localeCompare(b.fecha_creacion));
  const posicion = (t: Trabajo) => pendientes.findIndex((p) => p.id === t.id) + 1;
  const ordenados = [...trabajos].sort((a, b) => {
    // Activos arriba, después el resto del más nuevo al más viejo
    if (estaActivo(a) !== estaActivo(b)) return estaActivo(a) ? -1 : 1;
    return b.fecha_creacion.localeCompare(a.fecha_creacion);
  });

  const enviar = async () => {
    setEnviando(true);
    setErrorEnvio(null);
    try {
      const trabajo = await encolarEntrenamiento({
        datasets: elegidos,
        epocas: epocasNumero,
        imgsz: Number(imgsz),
        pesos_base: pesosBase,
        fraccion_validacion: Number(fraccion),
      });
      setTrabajos((lista) => [trabajo, ...lista]);
      setGeneracion((g) => g + 1);
      setElegidos([]);
    } catch (e) {
      setErrorEnvio(e);
    } finally {
      setEnviando(false);
    }
  };

  if (cargando) return <Spinner label="Cargando…" />;

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      {/* ===== Nuevo entrenamiento ===== */}
      <Card className={`${claseTarjeta} self-start lg:col-span-2`}>
        <CardBody className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className={claseEtiqueta}>Nuevo</p>
              <h2 className="text-2xl font-semibold">Entrenar un modelo</h2>
            </div>
            <BrainCircuit className="h-6 w-6 text-violet-500" />
          </div>

          {errorCarga != null && <PanelError error={errorCarga} />}

          {datasets.length === 0 ? (
            <p className={claseTextoSuave}>
              No hay aportes todavía.{" "}
              <Link to="/" className="font-medium text-blue-600 hover:underline dark:text-blue-400">
                Subí uno
              </Link>{" "}
              para poder entrenar.
            </p>
          ) : (
            <CheckboxGroup
              label="Aportes a usar"
              description={elegidos.length > 0 ? `${plural(imagenesElegidas, "imagen", "imágenes")} en total.` : "Elegí uno o más."}
              value={elegidos}
              onValueChange={setElegidos}
            >
              {datasets.map((d) => (
                <Checkbox key={d.id} value={d.id}>
                  <span className="font-medium">{d.nombre}</span>{" "}
                  <span className="text-sm text-slate-500">· {plural(d.total_imagenes, "imagen", "imágenes")}</span>
                </Checkbox>
              ))}
            </CheckboxGroup>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              type="number"
              label="Épocas"
              min={1}
              max={300}
              value={epocas}
              onValueChange={setEpocas}
              isInvalid={!epocasValidas}
              errorMessage="Entre 1 y 300"
            />
            <Select
              label="Tamaño de imagen"
              selectedKeys={[imgsz]}
              disallowEmptySelection
              onSelectionChange={(claves) => claveElegida(claves) && setImgsz(claveElegida(claves))}
              description="640 es el que usa el análisis"
            >
              {TAMANOS_IMAGEN.map((t) => (
                <SelectItem key={String(t)}>{`${t} px`}</SelectItem>
              ))}
            </Select>
          </div>

          <Select
            label="Validación"
            selectedKeys={[fraccion]}
            disallowEmptySelection
            onSelectionChange={(claves) => claveElegida(claves) && setFraccion(claveElegida(claves))}
            description={
              elegidos.length > 0
                ? `${plural(imagenesElegidas - imagenesValidacion, "imagen", "imágenes")} para entrenar y ${plural(imagenesValidacion, "imagen", "imágenes")} para validar y armar la evaluación (matriz de confusión, métricas por clase).`
                : "Parte de cada aporte que no se usa para entrenar: con ella se mide el modelo."
            }
          >
            {FRACCIONES_VALIDACION.map((f) => (
              <SelectItem key={String(f)}>{`${Math.round(f * 100)} % de cada aporte`}</SelectItem>
            ))}
          </Select>

          <Select
            label="Partir de"
            selectedKeys={[pesosBase]}
            disallowEmptySelection
            onSelectionChange={(claves) => claveElegida(claves) && setPesosBase(claveElegida(claves))}
            description="yolov8n.pt arranca de los pesos genéricos de Ultralytics; una versión del registro sigue entrenando ese modelo."
          >
            {[
              ...PESOS_BASE_OFICIALES.map((p) => <SelectItem key={p}>{p}</SelectItem>),
              ...modelos.map((m) => (
                <SelectItem key={m.version} textValue={m.version}>
                  {m.version}
                  {m.activo ? " (activo)" : ""}
                </SelectItem>
              )),
            ]}
          </Select>

          <p className={`flex items-start gap-2 text-sm ${claseTextoSuave}`}>
            <Clock className="mt-0.5 h-4 w-4 shrink-0" />
            Se entrena en CPU: con pocos cientos de imágenes, cada época puede llevar desde segundos hasta varios minutos.
          </p>

          <Button color="primary" onPress={enviar} isDisabled={!puedeEnviar} isLoading={enviando} className="dark:bg-blue-700">
            Encolar entrenamiento
          </Button>
          {elegidos.length > 0 && imagenesElegidas < 2 && (
            <p className="text-sm text-amber-700 dark:text-amber-300">Hacen falta al menos 2 imágenes para separar entrenamiento y validación.</p>
          )}
          {errorEnvio != null && <PanelError error={errorEnvio} />}
        </CardBody>
      </Card>

      {/* ===== Trabajos ===== */}
      <Card className={`${claseTarjeta} lg:col-span-3`}>
        <CardBody className="space-y-4">
          <div>
            <p className={claseEtiqueta}>Historial</p>
            <h2 className="text-2xl font-semibold">{plural(trabajos.length, "entrenamiento")}</h2>
          </div>
          {trabajos.length === 0 ? (
            <p className={claseTextoSuave}>Todavía no se lanzó ningún entrenamiento.</p>
          ) : (
            <ul className="space-y-3">
              {ordenados.map((t) => (
                <TarjetaTrabajo key={t.id} trabajo={t} nombreDataset={nombreDataset} posicionEnCola={posicion(t)} />
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
