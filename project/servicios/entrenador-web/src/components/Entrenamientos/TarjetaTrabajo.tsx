// =====================================
// src/components/Entrenamientos/TarjetaTrabajo.tsx
// =====================================
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, Chip, Modal, ModalBody, ModalContent, ModalFooter, ModalHeader, Progress } from "@heroui/react";
import { ArrowRight, Ban, Clock, XCircle } from "lucide-react";
import { cancelarEntrenamiento, type EstadoTrabajo, type Trabajo } from "../../services/EntrenamientoService";
import { useCuentaRegresiva } from "../../hooks/useCuentaRegresiva";
import { duracion, fecha, horaDentroDe, numero, plural, porcentaje } from "../../utils/formato";
import Metrica from "../comunes/Metrica";
import PanelError from "../comunes/PanelError";
import { claseTextoSuave } from "../comunes/estilos";

const ESTADOS: Record<EstadoTrabajo, { texto: string; color: "default" | "primary" | "success" | "danger" | "warning" }> = {
  pendiente: { texto: "En cola", color: "default" },
  ejecutando: { texto: "Entrenando", color: "primary" },
  completado: { texto: "Completado", color: "success" },
  fallido: { texto: "Falló", color: "danger" },
  cancelado: { texto: "Cancelado", color: "warning" },
};

/** Barra y tiempos de un trabajo en ejecución. */
function Avance({ trabajo }: { trabajo: Trabajo }) {
  const p = trabajo.progreso;
  const restante = useCuentaRegresiva(p?.segundos_restantes, p?.actualizado);
  const transcurrido = useCuentaRegresiva(p?.transcurrido_s, p?.actualizado, 1);

  if (trabajo.cancelacion_pedida) {
    return <Progress aria-label="Cancelando" label="Cancelando: corta al terminar el lote en curso…" isIndeterminate color="warning" />;
  }
  // Mientras prepara el dataset y el modelo, o evalúa al final, no hay forma de medir
  // cuánto falta: la barra se mueve sin porcentaje para mostrar que está trabajando
  if (!p || p.fase === "preparando") {
    return <Progress aria-label="Preparando" label="Preparando el dataset y el modelo…" isIndeterminate color="primary" />;
  }
  if (p.fase === "evaluando") {
    return (
      <Progress aria-label="Evaluando" label="Entrenamiento terminado: evaluando sobre las imágenes de validación…" isIndeterminate color="primary" />
    );
  }

  const fraccion = p.fraccion ?? 0;
  const epoca = Math.min(trabajo.epocas, Math.floor(fraccion * trabajo.epocas) + 1);
  return (
    <div className="space-y-1.5">
      <Progress
        aria-label="Avance del entrenamiento"
        label={`Época ${epoca} de ${trabajo.epocas}`}
        value={fraccion * 100}
        showValueLabel
        formatOptions={{ style: "percent", maximumFractionDigits: 0 }}
        color="primary"
      />
      <p className={`flex flex-wrap items-center gap-x-1.5 text-sm ${claseTextoSuave}`}>
        <Clock className="h-3.5 w-3.5" />
        {restante === undefined ? (
          "Calculando el tiempo restante…"
        ) : (
          <>
            Termina en <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">~{duracion(restante)}</span>
            <span>(cerca de las {horaDentroDe(restante)}, más la evaluación final)</span>
          </>
        )}
        {transcurrido !== undefined && <span>· lleva {duracion(transcurrido)}</span>}
      </p>
    </div>
  );
}

export default function TarjetaTrabajo({
  trabajo,
  nombreDataset,
  posicionEnCola,
  onActualizado,
}: {
  trabajo: Trabajo;
  nombreDataset: (id: string) => string;
  posicionEnCola?: number;
  onActualizado: (trabajo: Trabajo) => void;
}) {
  const estado = ESTADOS[trabajo.estado];
  const m = trabajo.metricas ?? {};
  const activo = trabajo.estado === "pendiente" || trabajo.estado === "ejecutando";

  const [confirmando, setConfirmando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [errorCancelacion, setErrorCancelacion] = useState<unknown>(null);

  const cancelar = async () => {
    setCancelando(true);
    setErrorCancelacion(null);
    try {
      onActualizado(await cancelarEntrenamiento(trabajo.id));
      setConfirmando(false);
    } catch (e) {
      setErrorCancelacion(e);
    } finally {
      setCancelando(false);
    }
  };

  return (
    <li className="space-y-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-700">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold">
            Trabajo <span className="font-mono">{trabajo.id}</span>
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {fecha(trabajo.fecha_creacion)} · {trabajo.epocas} épocas · imgsz {trabajo.imgsz} · desde {trabajo.pesos_base}
            {trabajo.fraccion_validacion !== undefined && ` · valida ${Math.round(trabajo.fraccion_validacion * 100)} %`}
            {trabajo.worker && trabajo.worker !== "cancelado" && (
              <>
                {" "}
                · worker <span className="font-mono">{trabajo.worker}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Chip size="sm" variant="flat" color={estado.color}>
            {estado.texto}
            {trabajo.estado === "pendiente" && posicionEnCola ? ` · ${posicionEnCola}º` : ""}
          </Chip>
          {activo && (
            <Button
              size="sm"
              variant="light"
              color="danger"
              startContent={<Ban className="h-3.5 w-3.5" />}
              isDisabled={trabajo.cancelacion_pedida}
              onPress={() => {
                setErrorCancelacion(null);
                setConfirmando(true);
              }}
            >
              Cancelar
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {trabajo.datasets.map((id) => (
          <Chip key={id} size="sm" variant="bordered">
            {nombreDataset(id)}
          </Chip>
        ))}
      </div>

      {trabajo.estado === "pendiente" && (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {/* Cada worker libre revisa la cola cada 5 segundos */}
          {posicionEnCola && posicionEnCola > 1
            ? `Tiene ${plural(posicionEnCola - 1, "entrenamiento")} adelante en la cola.`
            : "Es el próximo: arranca en cuanto haya un worker libre."}
        </p>
      )}

      {trabajo.estado === "ejecutando" && (
        <>
          <Avance trabajo={trabajo} />
          {trabajo.progreso_epocas > 0 && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metrica etiqueta="Pérdida" valor={numero(m.perdida, 3)} detalle={`época ${trabajo.progreso_epocas}`} />
              <Metrica etiqueta="mAP50-95" valor={porcentaje(m.map50_95)} />
              <Metrica etiqueta="mAP50" valor={porcentaje(m.map50)} />
              <Metrica etiqueta="Recall" valor={porcentaje(m.recall)} />
            </div>
          )}
        </>
      )}

      {trabajo.estado === "completado" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-emerald-50 px-4 py-3 text-sm dark:bg-emerald-950/40">
          <p>
            Publicó <span className="font-mono font-semibold">{trabajo.version_generada}</span> · mAP50-95{" "}
            <span className="font-semibold">{porcentaje(m.map50_95)}</span> (mejor época {m.epoca_mejor ?? "—"})
          </p>
          <Link
            to={`/modelos/${encodeURIComponent(trabajo.version_generada ?? "")}`}
            className="flex items-center gap-1 font-medium text-emerald-700 hover:underline dark:text-emerald-300"
          >
            Ver evaluación <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      )}

      {(trabajo.estado === "fallido" || trabajo.estado === "cancelado") && (
        <p
          className={`flex items-start gap-2 rounded-2xl px-4 py-3 text-sm ${
            trabajo.estado === "fallido"
              ? "bg-red-50 text-red-800 dark:bg-red-950/40 dark:text-red-200"
              : "bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
          }`}
        >
          {trabajo.estado === "fallido" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0" /> : <Ban className="mt-0.5 h-4 w-4 shrink-0" />}
          {trabajo.error ?? (trabajo.estado === "fallido" ? "Falló sin detalle. Revisá el log del worker." : "Cancelado.")}
        </p>
      )}

      <Modal isOpen={confirmando} onClose={() => !cancelando && setConfirmando(false)}>
        <ModalContent>
          <ModalHeader>Cancelar el entrenamiento</ModalHeader>
          <ModalBody className="space-y-3">
            {trabajo.estado === "pendiente" ? (
              <p>El trabajo todavía está en la cola: se saca y nunca se entrena.</p>
            ) : (
              <p>
                Se corta al terminar el lote en curso y se descarta lo entrenado hasta ahora
                {trabajo.progreso_epocas > 0 ? ` (${plural(trabajo.progreso_epocas, "época")} de ${trabajo.epocas})` : ""}: no se publica ninguna versión.
              </p>
            )}
            {errorCancelacion != null && <PanelError error={errorCancelacion} />}
          </ModalBody>
          <ModalFooter>
            <Button variant="light" onPress={() => setConfirmando(false)} isDisabled={cancelando}>
              Seguir entrenando
            </Button>
            <Button color="danger" onPress={cancelar} isLoading={cancelando}>
              Cancelar entrenamiento
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </li>
  );
}
