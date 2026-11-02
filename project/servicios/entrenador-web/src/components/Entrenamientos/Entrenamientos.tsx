// =====================================
// src/components/Entrenamientos/Entrenamientos.tsx
// =====================================
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Card, CardBody, Checkbox, CheckboxGroup, Input, Select, SelectItem, Spinner } from "@heroui/react";
import type { SharedSelection } from "@heroui/react";
import { BrainCircuit, Clock, Cpu, Zap } from "lucide-react";

import {
  cantidadValidacion,
  encolarEntrenamiento,
  listarDatasets,
  listarDispositivos,
  listarModelos,
  listarTrabajos,
  PESOS_BASE_OFICIALES,
  TAREA_DE_PESOS_OFICIALES,
  type Dataset,
  type Dispositivo,
  type Dispositivos,
  type Modelo,
  type Tarea,
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
// Épocas sin mejorar antes de cortar. Mismo valor que usa la API si no se manda
// nada; Ultralytics trae 100, que con corridas de 150 épocas no corta nunca
const PACIENCIA_POR_DEFECTO = 30;
const ESPERA_TRAS_CORTE_MS = 5000;

/** Clave elegida en un Select de selección simple (vacía si se deseleccionó). */
const claveElegida = (claves: SharedSelection) => (claves === "all" ? "" : String(Array.from(claves)[0] ?? ""));

export default function Entrenamientos() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [modelos, setModelos] = useState<Modelo[]>([]);
  const [trabajos, setTrabajos] = useState<Trabajo[]>([]);
  const [dispositivos, setDispositivos] = useState<Dispositivos | null>(null);
  const [generacion, setGeneracion] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<unknown>(null);

  const [elegidos, setElegidos] = useState<string[]>([]);
  const [epocas, setEpocas] = useState("50");
  const [paciencia, setPaciencia] = useState(String(PACIENCIA_POR_DEFECTO));
  const [imgsz, setImgsz] = useState("640");
  const [pesosBase, setPesosBase] = useState(PESOS_BASE_OFICIALES[0]);
  const [fraccion, setFraccion] = useState("0.25");
  const [dispositivo, setDispositivo] = useState<Dispositivo>("cpu");
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

  // Aparte del resto: que no haya GPU no impide entrenar en CPU, así que si este
  // pedido falla la pantalla sigue andando con la opción de GPU deshabilitada.
  useEffect(() => {
    listarDispositivos().then(setDispositivos).catch(() => setDispositivos(null));
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
  const pacienciaNumero = Number(paciencia);
  const pacienciaValida = Number.isInteger(pacienciaNumero) && pacienciaNumero >= 0 && pacienciaNumero <= 300;
  // Misma regla que la API: al menos una imagen de cada lado del split
  const splitValido = imagenesValidacion > 0 && imagenesElegidas - imagenesValidacion > 0;

  // La tarea no se elige: la traen los pesos de partida (ver TAREA_DE_PESOS_OFICIALES)
  const tarea: Tarea =
    TAREA_DE_PESOS_OFICIALES[pesosBase] ?? modelos.find((m) => m.version === pesosBase)?.tarea ?? "detect";
  // Mismo rechazo que la API, para avisarlo antes de encolar
  const sinContornos = tarea === "segment" ? aportesElegidos.filter((d) => !d.tiene_segmentacion) : [];
  const gpuDisponible = dispositivos?.gpu_disponible ?? false;

  const puedeEnviar =
    elegidos.length > 0 && splitValido && epocasValidas && pacienciaValida && sinContornos.length === 0 && !enviando;

  // Si se deja elegida la GPU y deja de estar disponible (se recargó la página
  // con el worker en CPU), el trabajo fallaría en el worker: vuelve a CPU
  useEffect(() => {
    if (dispositivo === "gpu" && dispositivos !== null && !gpuDisponible) setDispositivo("cpu");
  }, [dispositivo, dispositivos, gpuDisponible]);

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
        dispositivo,
        paciencia: pacienciaNumero,
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
                  {/* Solo cuando falta lo que hace falta para lo que se eligió entrenar */}
                  {tarea === "segment" && !d.tiene_segmentacion && (
                    <span className="text-sm text-amber-700 dark:text-amber-300"> · sin contornos</span>
                  )}
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
              description="Tope: con paciencia puede cortar antes."
            />
            <Input
              type="number"
              label="Paciencia"
              min={0}
              max={300}
              value={paciencia}
              onValueChange={setPaciencia}
              isInvalid={!pacienciaValida}
              errorMessage="Entre 0 y 300"
              description={
                pacienciaNumero === 0
                  ? "Desactivada: entrena todas las épocas aunque deje de mejorar."
                  : `Corta si el mAP de validación no mejora en ${pacienciaNumero} épocas seguidas. Se publica igual el mejor modelo, así que solo ahorra tiempo.`
              }
            />
          </div>

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
            description={
              tarea === "segment"
                ? "Entrena contornos: el análisis va a dibujar el borde de cada mancha y medir su superficie. Usa los polígonos de los aportes."
                : "Entrena cajas: el análisis solo va a marcar un punto por detección. Usa la caja que encierra cada polígono."
            }
          >
            {[
              ...PESOS_BASE_OFICIALES.map((p) => (
                <SelectItem key={p} textValue={p}>
                  {p}
                  <span className={`ml-1 text-xs ${claseTextoSuave}`}>
                    · {TAREA_DE_PESOS_OFICIALES[p] === "segment" ? "contornos" : "cajas"}, desde los pesos genéricos de
                    Ultralytics
                  </span>
                </SelectItem>
              )),
              ...modelos.map((m) => (
                <SelectItem key={m.version} textValue={m.version}>
                  {m.version}
                  {m.activo ? " (activo)" : ""}
                  <span className={`ml-1 text-xs ${claseTextoSuave}`}>
                    · {m.tarea === "segment" ? "contornos" : "cajas"}, sigue entrenando esa versión
                  </span>
                </SelectItem>
              )),
            ]}
          </Select>

          {/* Dónde entrenar. La GPU acorta un entrenamiento de horas a minutos,
              pero necesita que la imagen del worker esté construida con CUDA y
              que el contenedor tenga acceso a la placa: la API lo informa en
              /dispositivos y acá se explica qué falta cuando no está. */}
          <Select
            label="Entrenar en"
            selectedKeys={[dispositivo]}
            disallowEmptySelection
            onSelectionChange={(claves) => claveElegida(claves) && setDispositivo(claveElegida(claves) as Dispositivo)}
            disabledKeys={gpuDisponible ? [] : ["gpu"]}
            description={
              dispositivo === "gpu"
                ? `Lote de ${dispositivos?.lote_gpu ?? 16} imágenes en ${dispositivos?.gpus[0]?.nombre ?? "la GPU"}.`
                : `Lote de ${dispositivos?.lote_cpu ?? 2} imágenes. Con unos cientos de imágenes, cada época puede llevar desde segundos hasta varios minutos.`
            }
            startContent={dispositivo === "gpu" ? <Zap className="h-4 w-4 text-amber-500" /> : <Cpu className="h-4 w-4 text-slate-400" />}
          >
            <SelectItem key="cpu" textValue="CPU">
              CPU
              <span className={`ml-1 text-xs ${claseTextoSuave}`}>· siempre disponible, lento</span>
            </SelectItem>
            {/* Deshabilitada cuando no hay GPU; el motivo va abajo del Select,
                porque un item deshabilitado no recibe el hover de un tooltip */}
            <SelectItem key="gpu" textValue="GPU">
              GPU
              <span className={`ml-1 text-xs ${claseTextoSuave}`}>
                {gpuDisponible
                  ? `· ${dispositivos?.gpus[0]?.nombre}${dispositivos?.gpus[0] ? ` (${dispositivos.gpus[0].memoria_gb} GB)` : ""}`
                  : "· no disponible acá"}
              </span>
            </SelectItem>
          </Select>

          {!gpuDisponible && (
            <p className={`flex items-start gap-2 text-sm ${claseTextoSuave}`}>
              <Clock className="mt-0.5 h-4 w-4 shrink-0" />
              {dispositivos?.motivo ?? "No se pudo consultar si hay GPU disponible: se entrena en CPU."}
            </p>
          )}

          <Button color="primary" onPress={enviar} isDisabled={!puedeEnviar} isLoading={enviando} className="dark:bg-blue-700">
            Encolar entrenamiento
          </Button>
          {elegidos.length > 0 && !splitValido && (
            <p className="text-sm text-amber-700 dark:text-amber-300">
              Hace falta al menos una imagen para entrenar y otra para validar. Un aporte de una sola imagen va entero a
              entrenamiento: sumá aportes de más de una imagen.
            </p>
          )}
          {sinContornos.length > 0 && (
            <p className="text-sm text-amber-700 dark:text-amber-300">
              {sinContornos.length === 1
                ? `El aporte "${sinContornos[0].nombre}" no tiene`
                : `${sinContornos.length} de los aportes elegidos no tienen`}{" "}
              contornos, así que no sirven para entrenar segmentación: se etiquetaron con cajas, o se subieron antes de
              que el sistema guardara los polígonos. Volvé a subir esos ZIP de labelme (los polígonos ya están en sus
              JSON), o elegí unos pesos de cajas.
            </p>
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
                <TarjetaTrabajo
                  key={t.id}
                  trabajo={t}
                  nombreDataset={nombreDataset}
                  posicionEnCola={posicion(t)}
                  onActualizado={(actualizado) => setTrabajos((lista) => lista.map((x) => (x.id === actualizado.id ? actualizado : x)))}
                />
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
