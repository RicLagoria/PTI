// =====================================
// src/components/Modelos/Modelos.tsx
// =====================================
import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  CardBody,
  Chip,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Spinner,
} from "@heroui/react";
import { Link } from "react-router-dom";
import { BarChart3, CheckCircle2, Sprout, TrendingDown, TrendingUp } from "lucide-react";

import { activarModelo, listarDatasets, listarModelos, type Dataset, type Modelo } from "../../services/EntrenamientoService";
import { fecha, numero, plural, porcentaje } from "../../utils/formato";
import Metrica from "../comunes/Metrica";
import PanelError from "../comunes/PanelError";
import { claseTarjeta, claseTextoSuave } from "../comunes/estilos";

/** Diferencia de mAP50-95 contra el modelo activo, en puntos porcentuales. */
function Diferencia({ modelo, activo }: { modelo: Modelo; activo?: Modelo }) {
  const propio = modelo.meta.metricas?.map50_95;
  const referencia = activo?.meta.metricas?.map50_95;
  if (modelo.activo || propio === undefined || referencia === undefined) return null;
  const puntos = (propio - referencia) * 100;
  if (Math.abs(puntos) < 0.05) return <Chip size="sm" variant="flat">igual que el activo</Chip>;
  const mejor = puntos > 0;
  return (
    <Chip
      size="sm"
      variant="flat"
      color={mejor ? "success" : "danger"}
      startContent={mejor ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
    >
      {mejor ? "+" : ""}
      {numero(puntos, 1)} pts vs. activo
    </Chip>
  );
}

export default function Modelos() {
  const [modelos, setModelos] = useState<Modelo[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<unknown>(null);

  const [aActivar, setAActivar] = useState<Modelo | null>(null);
  const [activando, setActivando] = useState(false);
  const [errorActivacion, setErrorActivacion] = useState<unknown>(null);

  const recargar = useCallback(async () => {
    try {
      const [ms, ds] = await Promise.all([listarModelos(), listarDatasets()]);
      // El activo primero; el resto del más nuevo al más viejo
      setModelos(
        [...ms].sort((a, b) =>
          a.activo !== b.activo ? (a.activo ? -1 : 1) : (b.meta.fecha_creacion ?? "").localeCompare(a.meta.fecha_creacion ?? "")
        )
      );
      setDatasets(ds);
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

  const activo = modelos.find((m) => m.activo);
  const nombreDataset = (id: string) => datasets.find((d) => d.id === id)?.nombre ?? `${id} (eliminado)`;

  const confirmarActivacion = async () => {
    if (!aActivar) return;
    setActivando(true);
    setErrorActivacion(null);
    try {
      await activarModelo(aActivar.version);
      setAActivar(null);
      await recargar();
    } catch (e) {
      setErrorActivacion(e);
    } finally {
      setActivando(false);
    }
  };

  if (cargando) return <Spinner label="Cargando el registro…" />;
  if (errorCarga != null) return <PanelError error={errorCarga} />;

  return (
    <div className="space-y-4">
      <p className={`max-w-3xl text-sm ${claseTextoSuave}`}>
        <span className="font-semibold">mAP50-95</span> es la métrica principal: promedia qué tan bien coinciden las cajas
        predichas con las etiquetadas, desde un solape del 50% hasta uno del 95%. Es la que usa Ultralytics para elegir la
        mejor época de cada entrenamiento. Las métricas salen de las imágenes de validación de cada corrida, así que solo son
        comparables entre versiones entrenadas con los mismos aportes.
      </p>

      {modelos.length === 0 && <p className={claseTextoSuave}>El registro está vacío.</p>}

      <div className="grid gap-4 xl:grid-cols-2">
        {modelos.map((m) => {
          const met = m.meta.metricas ?? {};
          return (
            <Card
              key={m.version}
              className={`${claseTarjeta} ${m.activo ? "ring-2 ring-emerald-500 dark:ring-emerald-600" : ""}`}
            >
              <CardBody className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-xl font-semibold">
                      <span className="truncate font-mono">{m.version}</span>
                      {m.meta.origen === "semilla" && <Sprout className="h-5 w-5 shrink-0 text-emerald-500" aria-label="Semilla" />}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {m.meta.origen === "semilla" ? "Modelo del MVP, cargado como semilla" : `Entrenado desde ${m.meta.pesos_base ?? "—"}`}{" "}
                      · {fecha(m.meta.fecha_creacion)} · {numero(m.tamano_mb, 1)} MB
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Diferencia modelo={m} activo={activo} />
                    {m.activo ? (
                      <Chip color="success" variant="flat" startContent={<CheckCircle2 className="h-3.5 w-3.5" />}>
                        Activo
                      </Chip>
                    ) : (
                      <Button
                        size="sm"
                        color="primary"
                        variant="flat"
                        onPress={() => {
                          setErrorActivacion(null);
                          setAActivar(m);
                        }}
                      >
                        Activar
                      </Button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Metrica etiqueta="mAP50-95" valor={porcentaje(met.map50_95)} />
                  <Metrica etiqueta="mAP50" valor={porcentaje(met.map50)} />
                  <Metrica etiqueta="Precisión" valor={porcentaje(met.precision)} />
                  <Metrica etiqueta="Recall" valor={porcentaje(met.recall)} />
                </div>

                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                  <p>
                    Mejor época {met.epoca_mejor ?? "—"} de {met.epocas_entrenadas ?? "—"}
                    {m.meta.imgsz ? ` · imgsz ${m.meta.imgsz}` : ""}
                    {m.meta.imagenes_train !== undefined &&
                      ` · ${plural(m.meta.imagenes_train, "imagen", "imágenes")} de entrenamiento y ${numero(m.meta.imagenes_val)} de validación`}
                  </p>
                  {m.meta.datasets && m.meta.datasets.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {m.meta.datasets.map((id) => (
                        <Chip key={id} size="sm" variant="bordered">
                          {nombreDataset(id)}
                        </Chip>
                      ))}
                    </div>
                  )}
                  {m.meta.clases && (
                    <p className="text-xs text-slate-500 dark:text-slate-400">Clases: {m.meta.clases.join(", ")}</p>
                  )}
                </div>

                <Link
                  to={`/modelos/${encodeURIComponent(m.version)}`}
                  className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
                >
                  <BarChart3 className="h-4 w-4" /> Ver evaluación: por clase, matriz de confusión y curvas
                </Link>
              </CardBody>
            </Card>
          );
        })}
      </div>

      <Modal isOpen={aActivar !== null} onClose={() => !activando && setAActivar(null)}>
        <ModalContent>
          <ModalHeader>Activar {aActivar?.version}</ModalHeader>
          <ModalBody className="space-y-3">
            <p>
              Los próximos análisis de ortomosaicos van a usar <span className="font-mono font-semibold">{aActivar?.version}</span>
              {activo ? (
                <>
                  {" "}
                  en lugar de <span className="font-mono">{activo.version}</span>
                </>
              ) : null}
              . Si hay un análisis corriendo, sus próximos lotes ya se procesan con el modelo nuevo.
            </p>
            {activo && aActivar && (
              <div className="grid grid-cols-2 gap-2">
                <Metrica etiqueta={`mAP50-95 · ${activo.version}`} valor={porcentaje(activo.meta.metricas?.map50_95)} detalle="activo ahora" />
                <Metrica etiqueta={`mAP50-95 · ${aActivar.version}`} valor={porcentaje(aActivar.meta.metricas?.map50_95)} detalle="el que vas a activar" />
              </div>
            )}
            <p className={`text-sm ${claseTextoSuave}`}>Se puede volver a cualquier versión anterior activándola de nuevo.</p>
            {errorActivacion != null && <PanelError error={errorActivacion} />}
          </ModalBody>
          <ModalFooter>
            <Button variant="light" onPress={() => setAActivar(null)} isDisabled={activando}>
              Cancelar
            </Button>
            <Button color="primary" onPress={confirmarActivacion} isLoading={activando}>
              Activar
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
