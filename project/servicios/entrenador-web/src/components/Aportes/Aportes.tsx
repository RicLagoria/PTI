// =====================================
// src/components/Aportes/Aportes.tsx
// =====================================
import { useCallback, useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import {
  Button,
  Card,
  CardBody,
  Chip,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Progress,
  Spinner,
} from "@heroui/react";
import { CheckCircle2, FileArchive, Info, Tags, Trash2, Upload } from "lucide-react";

import {
  eliminarDataset,
  listarClases,
  listarDatasets,
  subirDataset,
  type Dataset,
} from "../../services/EntrenamientoService";
import { fecha, numero, plural, tamanoArchivo } from "../../utils/formato";
import PanelError from "../comunes/PanelError";
import { claseEtiqueta, claseTarjeta, claseTextoSuave } from "../comunes/estilos";

type Fase = "elegir" | "subiendo" | "procesando";

/** Avisos de un aporte aceptado: cosas que se ignoraron y conviene revisar. */
function avisosDe(d: Dataset): string[] {
  const avisos = [];
  if (d.imagenes_sin_anotar) avisos.push(`${plural(d.imagenes_sin_anotar, "imagen")} sin .json se ignoraron`);
  if (d.formas_ignoradas) avisos.push(`${plural(d.formas_ignoradas, "forma")} sin área (puntos o líneas) se ignoraron`);
  if (d.cajas_descartadas) avisos.push(`${plural(d.cajas_descartadas, "caja")} demasiado chicas se descartaron`);
  return avisos;
}

function ConteoPorClase({ dataset }: { dataset: Dataset }) {
  const total = Math.max(1, dataset.total_anotaciones);
  return (
    <div className="space-y-1.5">
      {Object.entries(dataset.anotaciones_por_clase).map(([clase, cantidad]) => (
        <div key={clase} className="flex items-center gap-2 text-xs">
          <span className="w-16 shrink-0 truncate text-slate-600 dark:text-slate-300">{clase}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(cantidad / total) * 100}%` }} />
          </div>
          <span className="w-8 shrink-0 text-right tabular-nums text-slate-500 dark:text-slate-400">{cantidad}</span>
        </div>
      ))}
    </div>
  );
}

export default function Aportes() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [clases, setClases] = useState<string[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<unknown>(null);

  const [archivo, setArchivo] = useState<File | null>(null);
  const [nombre, setNombre] = useState("");
  const [arrastrando, setArrastrando] = useState(false);
  const [fase, setFase] = useState<Fase>("elegir");
  const [progreso, setProgreso] = useState(0);
  const [resultado, setResultado] = useState<Dataset | null>(null);
  const [errorSubida, setErrorSubida] = useState<unknown>(null);
  const selectorArchivo = useRef<HTMLInputElement>(null);

  const [aBorrar, setABorrar] = useState<Dataset | null>(null);
  const [borrando, setBorrando] = useState(false);
  const [errorBorrado, setErrorBorrado] = useState<unknown>(null);

  const recargar = useCallback(async () => {
    try {
      const [lista, canonicas] = await Promise.all([listarDatasets(), listarClases()]);
      // Los más nuevos arriba
      setDatasets([...lista].sort((a, b) => b.fecha_creacion.localeCompare(a.fecha_creacion)));
      setClases(canonicas);
      setErrorCarga(null);
    } catch (e) {
      setErrorCarga(e);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  const elegirArchivo = (nuevo: File | undefined) => {
    if (!nuevo) return;
    setArchivo(nuevo);
    setResultado(null);
    setErrorSubida(null);
  };

  const soltar = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    if (fase === "elegir") elegirArchivo(e.dataTransfer.files[0]);
  };

  const subir = async () => {
    if (!archivo) return;
    setFase("subiendo");
    setProgreso(0);
    setResultado(null);
    setErrorSubida(null);
    try {
      const dataset = await subirDataset(archivo, nombre, setProgreso, () => setFase("procesando"));
      setResultado(dataset);
      setArchivo(null);
      setNombre("");
      if (selectorArchivo.current) selectorArchivo.current.value = "";
      await recargar();
    } catch (e) {
      setErrorSubida(e);
    } finally {
      setFase("elegir");
    }
  };

  const confirmarBorrado = async () => {
    if (!aBorrar) return;
    setBorrando(true);
    setErrorBorrado(null);
    try {
      await eliminarDataset(aBorrar.id);
      setABorrar(null);
      if (resultado?.id === aBorrar.id) setResultado(null);
      await recargar();
    } catch (e) {
      setErrorBorrado(e);
    } finally {
      setBorrando(false);
    }
  };

  const ocupado = fase !== "elegir";

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      {/* ===== Subida ===== */}
      <div className="space-y-6 lg:col-span-2">
        <Card className={claseTarjeta}>
          <CardBody className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className={claseEtiqueta}>Nuevo aporte</p>
                <h2 className="text-2xl font-semibold">Subir ZIP de labelme</h2>
              </div>
              <Upload className="h-6 w-6 text-sky-500" />
            </div>

            <div
              role="button"
              tabIndex={0}
              onClick={() => !ocupado && selectorArchivo.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !ocupado && selectorArchivo.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                if (!ocupado) setArrastrando(true);
              }}
              onDragLeave={() => setArrastrando(false)}
              onDrop={soltar}
              className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed p-6 text-center transition-colors ${
                arrastrando
                  ? "border-sky-500 bg-sky-50 dark:bg-sky-950/40"
                  : "border-slate-300 hover:border-sky-400 dark:border-slate-600"
              } ${ocupado ? "pointer-events-none opacity-60" : ""}`}
            >
              <FileArchive className="h-8 w-8 text-slate-400" />
              {archivo ? (
                <>
                  <p className="font-medium break-all">{archivo.name}</p>
                  <p className="text-xs text-slate-500">{tamanoArchivo(archivo.size)} · clic para cambiarlo</p>
                </>
              ) : (
                <>
                  <p className="font-medium">Arrastrá el ZIP acá o hacé clic para elegirlo</p>
                  <p className="text-xs text-slate-500">Las imágenes y los .json que guarda labelme, en cualquier estructura de carpetas</p>
                </>
              )}
              <input
                ref={selectorArchivo}
                type="file"
                accept=".zip,application/zip"
                className="hidden"
                onChange={(e) => elegirArchivo(e.target.files?.[0])}
              />
            </div>

            <Input
              label="Nombre del aporte"
              placeholder={archivo ? archivo.name.replace(/\.zip$/i, "") : "Por ejemplo: Lote norte, octubre"}
              description="Opcional. Si lo dejás vacío se usa el nombre del archivo."
              value={nombre}
              onValueChange={setNombre}
              isDisabled={ocupado}
            />

            {fase === "subiendo" && <Progress aria-label="Subiendo" label="Subiendo…" value={progreso} showValueLabel color="primary" />}
            {fase === "procesando" && (
              <Progress aria-label="Procesando" label="Convirtiendo las anotaciones…" isIndeterminate color="primary" />
            )}

            <Button color="primary" onPress={subir} isDisabled={!archivo || ocupado} isLoading={ocupado} className="dark:bg-blue-700">
              Subir aporte
            </Button>

            {errorSubida != null && <PanelError error={errorSubida} />}

            {resultado && (
              <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
                <p className="flex items-center gap-2 font-medium">
                  <CheckCircle2 className="h-4 w-4" />
                  "{resultado.nombre}" quedó guardado: {plural(resultado.total_imagenes, "imagen", "imágenes")},{" "}
                  {plural(resultado.total_anotaciones, "anotación", "anotaciones")}.
                </p>
                {avisosDe(resultado).length > 0 && (
                  <ul className="list-disc space-y-1 pl-5 text-amber-800 dark:text-amber-200">
                    {avisosDe(resultado).map((aviso) => (
                      <li key={aviso}>{aviso}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </CardBody>
        </Card>

        <Card className={claseTarjeta}>
          <CardBody className="space-y-3">
            <div className="flex items-center gap-2">
              <Tags className="h-5 w-5 text-emerald-500" />
              <h2 className="text-lg font-semibold">Etiquetas válidas</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {clases.map((clase, i) => (
                <Chip key={clase} variant="flat" color="success">
                  {i} · {clase}
                </Chip>
              ))}
            </div>
            <p className={`text-sm ${claseTextoSuave}`}>
              Las etiquetas se comparan por nombre, sin importar mayúsculas ni espacios de más. Cualquier otra rechaza el aporte entero.
              Rectángulos, polígonos y círculos se convierten a cajas; un .json sin formas cuenta como imagen de fondo.
            </p>
          </CardBody>
        </Card>
      </div>

      {/* ===== Listado ===== */}
      <Card className={`${claseTarjeta} lg:col-span-3`}>
        <CardBody className="space-y-4">
          <div>
            <p className={claseEtiqueta}>Guardados</p>
            <h2 className="text-2xl font-semibold">
              {cargando ? "Aportes" : `${plural(datasets.length, "aporte")}`}
            </h2>
          </div>

          {cargando ? (
            <Spinner label="Cargando aportes…" />
          ) : errorCarga != null ? (
            <PanelError error={errorCarga} />
          ) : datasets.length === 0 ? (
            <p className={claseTextoSuave}>Todavía no hay aportes. Subí el primero desde el panel de la izquierda.</p>
          ) : (
            <ul className="space-y-3">
              {datasets.map((d) => {
                const avisos = avisosDe(d);
                return (
                  <li key={d.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="truncate font-semibold">{d.nombre}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {fecha(d.fecha_creacion)} · {d.archivo_original} · <span className="font-mono">{d.id}</span>
                        </p>
                      </div>
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                        color="danger"
                        aria-label={`Eliminar ${d.nombre}`}
                        onPress={() => {
                          setErrorBorrado(null);
                          setABorrar(d);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="mt-3 grid gap-4 sm:grid-cols-[auto_1fr]">
                      <div className="flex gap-4 text-sm sm:flex-col sm:gap-1">
                        <span>
                          <span className="text-lg font-semibold tabular-nums">{numero(d.total_imagenes)}</span>{" "}
                          {d.total_imagenes === 1 ? "imagen" : "imágenes"}
                        </span>
                        <span>
                          <span className="text-lg font-semibold tabular-nums">{numero(d.total_anotaciones)}</span> cajas
                        </span>
                        {d.imagenes_sin_objetos > 0 && (
                          <span className="text-xs text-slate-500">{plural(d.imagenes_sin_objetos, "fondo")}</span>
                        )}
                      </div>
                      <ConteoPorClase dataset={d} />
                    </div>

                    {avisos.length > 0 && (
                      <p className="mt-3 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-300">
                        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        {avisos.join(" · ")}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </CardBody>
      </Card>

      <Modal isOpen={aBorrar !== null} onClose={() => !borrando && setABorrar(null)}>
        <ModalContent>
          <ModalHeader>Eliminar aporte</ModalHeader>
          <ModalBody className="space-y-3">
            <p>
              ¿Eliminar <span className="font-semibold">{aBorrar?.nombre}</span>? Se borran sus{" "}
              {plural(aBorrar?.total_imagenes ?? 0, "imagen", "imágenes")} y no se puede deshacer.
            </p>
            <p className={`text-sm ${claseTextoSuave}`}>
              Las versiones del modelo ya entrenadas con este aporte no cambian; los entrenamientos en cola que lo usen van a fallar.
            </p>
            {errorBorrado != null && <PanelError error={errorBorrado} />}
          </ModalBody>
          <ModalFooter>
            <Button variant="light" onPress={() => setABorrar(null)} isDisabled={borrando}>
              Cancelar
            </Button>
            <Button color="danger" onPress={confirmarBorrado} isLoading={borrando}>
              Eliminar
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
