// =====================================
// src/components/Entrenamientos/TarjetaTrabajo.tsx
// =====================================
import { Link } from "react-router-dom";
import { Chip, Progress } from "@heroui/react";
import { ArrowRight, XCircle } from "lucide-react";
import type { EstadoTrabajo, Trabajo } from "../../services/EntrenamientoService";
import { fecha, numero, plural, porcentaje } from "../../utils/formato";
import Metrica from "../comunes/Metrica";

const ESTADOS: Record<EstadoTrabajo, { texto: string; color: "default" | "primary" | "success" | "danger" }> = {
  pendiente: { texto: "En cola", color: "default" },
  ejecutando: { texto: "Entrenando", color: "primary" },
  completado: { texto: "Completado", color: "success" },
  fallido: { texto: "Falló", color: "danger" },
};

export default function TarjetaTrabajo({
  trabajo,
  nombreDataset,
  posicionEnCola,
}: {
  trabajo: Trabajo;
  nombreDataset: (id: string) => string;
  posicionEnCola?: number;
}) {
  const estado = ESTADOS[trabajo.estado];
  const m = trabajo.metricas ?? {};

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
            {trabajo.worker && (
              <>
                {" "}
                · worker <span className="font-mono">{trabajo.worker}</span>
              </>
            )}
          </p>
        </div>
        <Chip size="sm" variant="flat" color={estado.color}>
          {estado.texto}
          {trabajo.estado === "pendiente" && posicionEnCola ? ` · ${posicionEnCola}º` : ""}
        </Chip>
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
          <Progress
            aria-label="Avance del entrenamiento"
            label={
              m.evaluando
                ? "Entrenado: evaluando sobre las imágenes de validación…"
                : trabajo.progreso_epocas
                  ? `Época ${trabajo.progreso_epocas} de ${trabajo.epocas}`
                  : "Preparando el dataset…"
            }
            value={trabajo.progreso_epocas}
            maxValue={trabajo.epocas}
            isIndeterminate={!trabajo.progreso_epocas || m.evaluando}
            showValueLabel={!!trabajo.progreso_epocas && !m.evaluando}
            color="primary"
          />
          {trabajo.progreso_epocas > 0 && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metrica etiqueta="Pérdida" valor={numero(m.perdida, 3)} />
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

      {trabajo.estado === "fallido" && (
        <p className="flex items-start gap-2 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-200">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {trabajo.error ?? "Falló sin detalle. Revisá el log del worker."}
        </p>
      )}
    </li>
  );
}
