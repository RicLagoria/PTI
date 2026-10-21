// =====================================
// src/components/Modelos/DetalleModelo.tsx
// =====================================
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, CardBody, Chip, Spinner } from "@heroui/react";
import { AlertTriangle, ArrowLeft, CheckCircle2, Crosshair, Info, Sprout } from "lucide-react";

import {
  listarModelos,
  obtenerDetalleModelo,
  urlImagenModelo,
  type DetalleModelo as Detalle,
  type MetricasPorClase,
  type Modelo,
} from "../../services/EntrenamientoService";
import { fecha, numero, porcentaje } from "../../utils/formato";
import GraficoLineas from "../graficos/GraficoLineas";
import MatrizConfusion from "../graficos/MatrizConfusion";
import Metrica from "../comunes/Metrica";
import PanelError from "../comunes/PanelError";
import { claseEtiqueta, claseTarjeta, claseTextoSuave } from "../comunes/estilos";

// Con menos instancias que esto en validación, la métrica de una clase cambia
// mucho con un solo acierto o error: se marca como poco confiable
const INSTANCIAS_CONFIABLES = 30;

function Seccion({ etiqueta, titulo, children, explicacion }: { etiqueta: string; titulo: string; explicacion?: ReactNode; children: ReactNode }) {
  return (
    <Card className={claseTarjeta}>
      <CardBody className="space-y-4">
        <div>
          <p className={claseEtiqueta}>{etiqueta}</p>
          <h2 className="text-xl font-semibold">{titulo}</h2>
          {explicacion && <p className={`mt-1 max-w-3xl text-sm ${claseTextoSuave}`}>{explicacion}</p>}
        </div>
        {children}
      </CardBody>
    </Card>
  );
}

function TablaPorClase({ filas }: { filas: MetricasPorClase[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-sm">
        <thead className="text-left text-xs text-slate-500 dark:text-slate-400">
          <tr>
            <th className="py-2 pr-4 font-medium">Clase</th>
            <th className="py-2 pr-4 text-right font-medium">Instancias</th>
            <th className="py-2 pr-4 text-right font-medium">Precisión</th>
            <th className="py-2 pr-4 text-right font-medium">Recall</th>
            <th className="py-2 pr-4 text-right font-medium">mAP50</th>
            <th className="py-2 text-right font-medium">mAP50-95</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {filas.map((f) => (
            <tr key={f.clase} className="border-t border-slate-100 dark:border-slate-700">
              <td className="py-2 pr-4 font-medium">
                {f.clase}
                {f.instancias === 0 ? (
                  <Chip size="sm" variant="flat" className="ml-2">sin instancias</Chip>
                ) : f.instancias < INSTANCIAS_CONFIABLES ? (
                  <Chip size="sm" variant="flat" color="warning" startContent={<AlertTriangle className="h-3 w-3" />} className="ml-2">
                    pocas instancias
                  </Chip>
                ) : null}
              </td>
              <td className="py-2 pr-4 text-right">{numero(f.instancias)}</td>
              <td className="py-2 pr-4 text-right">{porcentaje(f.precision ?? undefined)}</td>
              <td className="py-2 pr-4 text-right">{porcentaje(f.recall ?? undefined)}</td>
              <td className="py-2 pr-4 text-right">{porcentaje(f.map50 ?? undefined)}</td>
              <td className="py-2 text-right font-semibold">{porcentaje(f.map50_95 ?? undefined)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DetalleModelo() {
  const { version = "" } = useParams();
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let vigente = true;
    Promise.all([obtenerDetalleModelo(version), listarModelos()])
      .then(([d, ms]) => {
        if (!vigente) return;
        setDetalle(d);
        setModelo(ms.find((m) => m.version === version) ?? null);
      })
      .catch((e) => vigente && setError(e));
    return () => {
      vigente = false;
    };
  }, [version]);

  const volver = (
    <Link to="/modelos" className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">
      <ArrowLeft className="h-4 w-4" /> Todas las versiones
    </Link>
  );

  if (error != null) return <div className="space-y-4">{volver}<PanelError error={error} /></div>;
  if (!detalle) return <Spinner label="Cargando la evaluación…" />;

  const ev = detalle.evaluacion;
  const meta = modelo?.meta ?? {};
  const metricas = ev?.metricas ?? meta.metricas ?? {};
  const historial = detalle.historial;
  const epocaMejor = meta.metricas?.epoca_mejor;

  return (
    <div className="space-y-6">
      {volver}

      {/* ===== Encabezado y resumen ===== */}
      <Card className={claseTarjeta}>
        <CardBody className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-2xl font-semibold">
                <span className="truncate font-mono">{version}</span>
                {meta.origen === "semilla" && <Sprout className="h-5 w-5 shrink-0 text-emerald-500" aria-label="Semilla" />}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {meta.origen === "semilla" ? "Modelo del MVP, cargado como semilla" : `Entrenado desde ${meta.pesos_base ?? "—"}`} ·{" "}
                {fecha(meta.fecha_creacion)}
                {meta.imagenes_train !== undefined &&
                  ` · ${numero(meta.imagenes_train)} imágenes de entrenamiento y ${numero(meta.imagenes_val)} de validación (${numero((meta.fraccion_validacion ?? 0) * 100)} %)`}
              </p>
            </div>
            {modelo?.activo && (
              <Chip color="success" variant="flat" startContent={<CheckCircle2 className="h-3.5 w-3.5" />}>
                Activo
              </Chip>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Metrica etiqueta="mAP50-95" valor={porcentaje(metricas.map50_95)} />
            <Metrica etiqueta="mAP50" valor={porcentaje(metricas.map50)} />
            <Metrica etiqueta="Precisión" valor={porcentaje(metricas.precision)} />
            <Metrica etiqueta="Recall" valor={porcentaje(metricas.recall)} />
            <div className="col-span-2 rounded-2xl border border-blue-200 bg-blue-50 p-4 md:col-span-1 dark:border-blue-900 dark:bg-blue-950/40">
              <p className="flex items-center gap-1.5 text-xs text-blue-700 dark:text-blue-300">
                <Crosshair className="h-3.5 w-3.5" /> Umbral recomendado
              </p>
              <p className="mt-1 text-xl font-semibold">{ev?.umbral_recomendado != null ? porcentaje(ev.umbral_recomendado) : "—"}</p>
              <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400">
                {ev?.umbral_recomendado != null ? "Usalo como confianza mínima al analizar" : ev ? "El modelo casi no acierta" : "Sin evaluación"}
              </p>
            </div>
          </div>

          {ev ? (
            <p className={`flex items-start gap-2 text-sm ${claseTextoSuave}`}>
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              Medido sobre las imágenes de validación de este entrenamiento, las mismas con las que se eligió la mejor época: es una estimación algo optimista, y solo se compara de igual a igual con versiones entrenadas con los mismos aportes.
            </p>
          ) : (
            <p className="flex items-start gap-2 rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              {meta.error_evaluacion
                ? `La evaluación falló después de entrenar: ${meta.error_evaluacion}`
                : "Esta versión no tiene evaluación numérica: se entrenó fuera del sistema y su dataset no está acá. Abajo quedan los gráficos que guardó Ultralytics."}
            </p>
          )}
        </CardBody>
      </Card>

      {ev && (
        <>
          <Seccion
            etiqueta="Por clase"
            titulo="Qué tan bien detecta cada clase"
            explicacion={
              <>
                El promedio esconde diferencias: una clase puede andar bien y otra no detectarse nunca. Con menos de {INSTANCIAS_CONFIABLES} instancias en validación, un solo acierto o error mueve mucho la métrica.
              </>
            }
          >
            <TablaPorClase filas={ev.por_clase} />
          </Seccion>

          <Seccion
            etiqueta="Matriz de confusión"
            titulo="Qué predice el modelo para cada clase real"
            explicacion={
              <>
                Cada fila es lo que había etiquetado; cada columna, lo que vio el modelo con confianza de al menos{" "}
                {porcentaje(ev.matriz_confusion.umbral)}. La columna <em>fondo</em> son objetos que no vio; la fila <em>fondo</em>, falsas alarmas donde no había nada. Una caja cuenta como acierto si se superpone al menos {porcentaje(ev.matriz_confusion.iou)} con la real.
              </>
            }
          >
            <MatrizConfusion etiquetas={ev.matriz_confusion.etiquetas} filas={ev.matriz_confusion.filas_reales} />
          </Seccion>

          {ev.curvas_confianza && (
            <Seccion
              etiqueta="Umbral de confianza"
              titulo="Qué pasa al exigir más confianza"
              explicacion="Subir el umbral deja menos falsas alarmas (sube la precisión) pero se escapan más objetos (baja el recall). El recomendado es el que mejor equilibra las dos (máximo F1)."
            >
              <GraficoLineas
                titulo="Precisión, recall y F1 según el umbral de confianza"
                x={ev.curvas_confianza.confianza}
                series={[
                  { clave: "precision", nombre: "Precisión", color: "var(--serie-1)", valores: ev.curvas_confianza.precision },
                  { clave: "recall", nombre: "Recall", color: "var(--serie-2)", valores: ev.curvas_confianza.recall },
                  { clave: "f1", nombre: "F1", color: "var(--serie-3)", valores: ev.curvas_confianza.f1 },
                ]}
                etiquetaX="Confianza"
                formatoX={(v) => porcentaje(v)}
                formatoY={(v) => porcentaje(v)}
                dominioY={[0, 1]}
                marcador={ev.umbral_recomendado != null ? { x: ev.umbral_recomendado, etiqueta: `recomendado ${porcentaje(ev.umbral_recomendado)}` } : undefined}
              />
            </Seccion>
          )}
        </>
      )}

      {historial.length > 0 && (
        <Seccion
          etiqueta="Entrenamiento"
          titulo="Cómo evolucionó época a época"
          explicacion="Si la pérdida de validación sube mientras la de entrenamiento sigue bajando, el modelo está memorizando las imágenes de entrenamiento: hacen falta más datos o menos épocas."
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">Pérdida</h3>
              <GraficoLineas
                titulo="Pérdida de entrenamiento y de validación por época"
                x={historial.map((h) => h.epoca)}
                series={[
                  { clave: "train", nombre: "Entrenamiento", color: "var(--serie-1)", valores: historial.map((h) => h.perdida_train) },
                  { clave: "val", nombre: "Validación", color: "var(--serie-2)", valores: historial.map((h) => h.perdida_val) },
                ]}
                etiquetaX="Época"
                formatoX={(v) => numero(v)}
                formatoY={(v) => numero(v, 2)}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold">mAP50-95 en validación</h3>
              <GraficoLineas
                titulo="mAP50-95 de validación por época"
                x={historial.map((h) => h.epoca)}
                series={[{ clave: "map", nombre: "mAP50-95", color: "var(--serie-1)", valores: historial.map((h) => h.map50_95) }]}
                etiquetaX="Época"
                formatoX={(v) => numero(v)}
                formatoY={(v) => porcentaje(v)}
                marcador={epocaMejor ? { x: epocaMejor, etiqueta: `mejor: época ${epocaMejor}` } : undefined}
              />
            </div>
          </div>
        </Seccion>
      )}

      {!ev && detalle.imagenes.includes("confusion_matrix.png") && (
        <Seccion etiqueta="Gráfico de Ultralytics" titulo="Matriz de confusión">
          <img
            src={urlImagenModelo(version, "confusion_matrix.png")}
            alt={`Matriz de confusión de ${version} generada por Ultralytics`}
            className="mx-auto max-h-[36rem] rounded-xl bg-white"
          />
        </Seccion>
      )}
    </div>
  );
}
