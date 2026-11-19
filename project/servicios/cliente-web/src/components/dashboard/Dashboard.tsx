import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardBody, Chip, Button, Tooltip, Drawer, DrawerContent, DrawerHeader, DrawerBody } from "@heroui/react";
import { CloudRain, Thermometer, Wind, Sparkles, Leaf, Gauge, Cpu, Images, Info, ShieldCheck } from "lucide-react";
import { fetchCurrentWeather, type WeatherResponse } from "../../services/WeatherService";
import { listarImagenes } from "../../services/ImagenesService";
import { obtenerEstadisticas, type Estadisticas } from "../../services/EstadisticasService";

/** Ícono "i" con tooltip, para explicar de dónde sale cada métrica sin alargar la tarjeta. */
function InfoTip({ texto }: { texto: ReactNode }) {
  return (
    <Tooltip content={<div className="max-w-64 text-xs">{texto}</div>} placement="top" showArrow>
      <Info className="h-3.5 w-3.5 shrink-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300" />
    </Tooltip>
  );
}

const weatherCodeToText = (code: number) => {
  const mapping: Record<number, string> = {
    0: "Despejado",
    1: "Principalmente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla congelante",
    51: "Llovizna ligera",
    53: "Llovizna moderada",
    55: "Llovizna intensa",
    61: "Lluvia ligera",
    63: "Lluvia moderada",
    65: "Lluvia intensa",
    71: "Nieve ligera",
    73: "Nieve moderada",
    75: "Nieve intensa",
    80: "Lluvias dispersas",
    81: "Lluvias frecuentes",
    82: "Lluvias intensas",
  };
  return mapping[code] ?? "Clima variable";
};

const CLASE_LABEL: Record<string, string> = {
  maleza: "Maleza",
  falla: "Falla de cultivo",
  camino: "Camino",
  lodazal: "Lodazal",
};

function formatearFechaCorta(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

type GraficoKpi =
  | { tipo: "torta"; segmentos: { label: string; value: number; color: string }[] }
  | { tipo: "gauge"; value: number; meta: number; unidad: string };

/** Torta simple en SVG: no amerita sumar una librería de gráficos para 2 casos. */
function DonutKpi({ segmentos, tamano = 180 }: { segmentos: { label: string; value: number; color: string }[]; tamano?: number }) {
  const total = segmentos.reduce((s, d) => s + d.value, 0);
  const radio = tamano / 2 - 16;
  const circunferencia = 2 * Math.PI * radio;
  let acumulado = 0;
  return (
    <div className="flex flex-col items-center gap-4">
      <svg width={tamano} height={tamano} viewBox={`0 0 ${tamano} ${tamano}`}>
        <g transform={`translate(${tamano / 2}, ${tamano / 2}) rotate(-90)`}>
          {total <= 0 ? (
            <circle r={radio} fill="none" stroke="#cbd5e1" strokeWidth={24} />
          ) : (
            segmentos.map((seg) => {
              const frac = seg.value / total;
              const dash = frac * circunferencia;
              const offset = -acumulado * circunferencia;
              acumulado += frac;
              return (
                <circle
                  key={seg.label}
                  r={radio}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={24}
                  strokeDasharray={`${dash} ${circunferencia - dash}`}
                  strokeDashoffset={offset}
                />
              );
            })
          )}
        </g>
      </svg>
      <div className="flex flex-wrap justify-center gap-4">
        {segmentos.map((seg) => (
          <div key={seg.label} className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
            {seg.label} · {total > 0 ? Math.round((seg.value / total) * 100) : 0}%
          </div>
        ))}
      </div>
    </div>
  );
}

/** Barra contra la meta: para KPI que no son "partes de un todo" (un promedio, un tiempo), donde una torta no tendría sentido. */
function GaugeKpi({ value, meta, unidad, cumplida }: { value: number; meta: number; unidad: string; cumplida: boolean | null }) {
  const pct = Math.max(0, Math.min(100, Math.round((value / meta) * 100)));
  const color = cumplida === true ? "bg-emerald-500" : cumplida === false ? "bg-rose-500" : "bg-slate-400";
  const etiqueta = cumplida === null ? "Referencia" : "Meta";
  return (
    <div className="w-full max-w-xs space-y-2">
      <div className="flex items-end justify-between">
        <span className="text-3xl font-bold">{value}{unidad}</span>
        <span className="text-sm text-slate-500 dark:text-slate-400">{etiqueta}: {meta}{unidad}</span>
      </div>
      <div className="h-3 w-full rounded-full bg-slate-100 dark:bg-slate-700">
        <div className={`h-3 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-slate-400 dark:text-slate-500">{pct}% de esa {etiqueta.toLowerCase()}</p>
    </div>
  );
}

export default function Dashboard() {
  const navegar = useNavigate();
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [loadingClima, setLoadingClima] = useState(false);
  const [errorClima, setErrorClima] = useState<string | null>(null);
  const [sinOrtomosaico, setSinOrtomosaico] = useState(false);

  const [stats, setStats] = useState<Estadisticas | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [errorStats, setErrorStats] = useState<string | null>(null);
  const [kpiAbierto, setKpiAbierto] = useState<string | null>(null);

  useEffect(() => {
    const loadWeather = async () => {
      setLoadingClima(true);
      setErrorClima(null);
      try {
        // El clima corresponde al campo del último ortomosaico subido, no a una
        // ubicación fija: se toma el centro de sus bounds.
        const imagenes = await listarImagenes();
        const ultima = imagenes[0];
        if (!ultima) {
          setSinOrtomosaico(true);
          return;
        }
        const [[sur, oeste], [norte, este]] = ultima.bounds;
        const lat = (sur + norte) / 2;
        const lon = (oeste + este) / 2;
        const currentWeather = await fetchCurrentWeather(lat, lon);
        setWeather(currentWeather);
      } catch {
        setErrorClima("No se pudo cargar el clima. Revisá tu conexión o la API.");
      } finally {
        setLoadingClima(false);
      }
    };

    const loadStats = async () => {
      setLoadingStats(true);
      setErrorStats(null);
      try {
        setStats(await obtenerEstadisticas());
      } catch (err) {
        setErrorStats(err instanceof Error ? err.message : "No se pudieron calcular las estadísticas.");
      } finally {
        setLoadingStats(false);
      }
    };

    loadWeather();
    loadStats();
  }, []);

  const sinAnalisis = stats !== null && stats.total_analisis === 0;
  const modeloReciente = stats?.modelo.por_version[0] ?? null;
  const historialEficiencia = stats?.eficiencia.historial ?? [];
  const maxSegPorCelda = Math.max(1, ...historialEficiencia.map((h) => h.seg_por_celda));

  /** Estado del KPI contra su meta: true = cumple, false = por debajo, null = sin umbral fijo (solo seguimiento). */
  type EstadoMeta = boolean | null;

  type KpiCard = {
    label: string;
    value: string;
    meta: string;
    cumplida: EstadoMeta;
    sub: string;
    tip: string;
    icon: typeof Leaf;
    color: "success" | "warning" | "primary" | "secondary";
    descripcion: string;
    indicador: string;
    unidadMedida: string;
    frecuencia: string;
    herramienta: string;
    grafico: GraficoKpi | null;
  };

  const pctCobertura = stats?.cobertura.pct_cobertura ?? 0;
  const completados = stats?.confiabilidad.completados ?? 0;
  const conError = stats?.confiabilidad.con_error ?? 0;

  const objetivos: { titulo: string; kpis: KpiCard[] }[] = [
    {
      titulo: "Objetivo 1 · Garantizar la calidad de detección del modelo de IA",
      kpis: [
        {
          label: "Cobertura de malezas",
          value: sinAnalisis ? "—" : `${pctCobertura}%`,
          meta: "Seguimiento de tendencia (reducir interanual con manejo localizado, a validar en campo), con primera revisión en diciembre de 2026",
          cumplida: null,
          sub: "Celdas con maleza / celdas inspeccionadas, último análisis de cada imagen",
          tip: "De cada ortomosaico se toma solo su análisis completo más reciente (no se suman corridas repetidas). Es el % de esas celdas donde se detectó al menos una maleza.",
          icon: Leaf,
          color: "success",
          descripcion: "Mide qué proporción de la superficie analizada presenta al menos una detección de maleza, para dimensionar el alcance del problema por lote.",
          indicador: "% de celdas con detección de maleza sobre celdas inspeccionadas",
          unidadMedida: "Porcentaje (%)",
          frecuencia: "Por cada análisis ejecutado",
          herramienta: "Consulta SQL sobre la tabla detecciones (PostGIS), calculada en estadisticas_dashboard (backend) y mostrada en este Dashboard",
          grafico: sinAnalisis
            ? null
            : {
                tipo: "torta",
                segmentos: [
                  { label: "Con maleza detectada", value: pctCobertura, color: "#16a34a" },
                  { label: "Sin maleza detectada", value: Math.max(0, 100 - pctCobertura), color: "#cbd5e1" },
                ],
              },
        },
        {
          label: "Confianza del modelo",
          value: modeloReciente ? `${Math.round(modeloReciente.confianza_promedio)}%` : "—",
          meta: "Seguimiento de tendencia: se espera que suba con cada reentrenamiento (no equivale al mAP@0.5 de una evaluación independiente), con primera revisión en diciembre de 2026",
          cumplida: null,
          sub: modeloReciente ? `Versión ${modeloReciente.version_modelo} · ${modeloReciente.corridas} corridas` : "Sin corridas con detecciones aún",
          tip: "Promedio de confianza de todas las detecciones hechas con la versión de modelo que corrió más recientemente. Depende también del umbral mínimo usado en cada análisis: un umbral bajo admite detecciones más dudosas y baja el promedio sin que el modelo haya empeorado.",
          icon: Cpu,
          color: "primary",
          descripcion: "Nivel de confianza promedio que devuelve el modelo YOLOv8 en sus detecciones, para la versión de modelo que corrió más recientemente. No es una meta fija: varía con el umbral mínimo de cada análisis y va a moverse a medida que se reentrena el modelo.",
          indicador: "Confianza promedio de las detecciones aceptadas (distinto de mAP; ver informe PTI sección 5.4)",
          unidadMedida: "Porcentaje (%)",
          frecuencia: "Por versión de modelo / por análisis",
          herramienta: "Cálculo agregado en estadisticas_dashboard (backend), mostrado en este Dashboard",
          grafico: modeloReciente ? { tipo: "gauge", value: Math.round(modeloReciente.confianza_promedio), meta: 75, unidad: "%" } : null,
        },
      ],
    },
    {
      titulo: "Objetivo 2 · Asegurar la calidad y confiabilidad del servicio de análisis",
      kpis: [
        {
          label: "Tiempo de análisis por celda",
          value: stats?.eficiencia.promedio_seg_por_celda != null ? `${stats.eficiencia.promedio_seg_por_celda}s` : "—",
          meta: "Meta: ≤ 100s por celda, a cumplir para diciembre de 2026",
          cumplida: stats?.eficiencia.promedio_seg_por_celda != null ? stats.eficiencia.promedio_seg_por_celda <= 100 : null,
          sub: "Promedio de las últimas 10 corridas completas",
          tip: "Tiempo total del análisis dividido su cantidad de celdas, para las últimas 10 corridas completas.",
          icon: Gauge,
          color: "secondary",
          descripcion: "Tiempo que tarda el sistema en procesar cada celda del recorrido, para medir la eficiencia del servicio de análisis.",
          indicador: "Segundos promedio por celda procesada, últimas 10 corridas completas",
          unidadMedida: "Segundos por celda",
          frecuencia: "Por análisis ejecutado",
          herramienta: "Medido en el backend a partir de fecha_inicio/fecha_fin de cada análisis (tabla analisis)",
          grafico: stats?.eficiencia.promedio_seg_por_celda != null ? { tipo: "gauge", value: stats.eficiencia.promedio_seg_por_celda, meta: 100, unidad: "s" } : null,
        },
        {
          label: "Análisis sin error",
          value: stats?.confiabilidad.pct_sin_error != null ? `${stats.confiabilidad.pct_sin_error}%` : "—",
          meta: "Meta: ≥ 95% sin error, a cumplir para diciembre de 2026",
          cumplida: stats?.confiabilidad.pct_sin_error != null ? stats.confiabilidad.pct_sin_error >= 95 : null,
          sub: stats ? `${completados} completos · ${conError} con error` : "—",
          tip: "% de análisis que terminaron en estado \"completo\" sobre el total de análisis finalizados (completos + con error). Mide la confiabilidad del pipeline.",
          icon: ShieldCheck,
          color: "warning",
          descripcion: "Qué porcentaje de los análisis ejecutados termina en estado \"completo\" en vez de \"error\", para medir la confiabilidad del pipeline.",
          indicador: "% de análisis completos sobre el total de análisis finalizados (completos + con error)",
          unidadMedida: "Porcentaje (%)",
          frecuencia: "Semanal / acumulado",
          herramienta: "Consulta sobre el campo estado de la tabla analisis (Postgres), calculada en estadisticas_dashboard (backend)",
          grafico:
            completados + conError > 0
              ? {
                  tipo: "torta",
                  segmentos: [
                    { label: "Completos", value: completados, color: "#16a34a" },
                    { label: "Con error", value: conError, color: "#dc2626" },
                  ],
                }
              : null,
        },
      ],
    },
  ];

  const otrosIndicadores = [
    {
      label: "Maleza principal",
      value: sinAnalisis || !stats?.cobertura.clase_principal ? "—" : (CLASE_LABEL[stats.cobertura.clase_principal] ?? stats.cobertura.clase_principal),
      sub: sinAnalisis ? "Todavía no hay análisis corridos" : `${stats?.cobertura.detecciones_totales ?? 0} detecciones en total`,
      tip: "La clase con más detecciones acumuladas, contando el último análisis completo de cada imagen.",
      icon: Sparkles,
      color: "warning" as const,
    },
    {
      label: "Ortomosaicos / Análisis",
      value: stats ? `${stats.total_ortomosaicos} / ${stats.total_analisis}` : "—",
      sub: stats?.ultima_actualizacion ? `Último análisis: ${formatearFechaCorta(stats.ultima_actualizacion)}` : "Subí una imagen para empezar",
      tip: "Fotos subidas por todo el equipo / corridas de análisis totales (incluye las que fallaron o quedaron a medias).",
      icon: Images,
      color: "secondary" as const,
    },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap justify-end gap-2">
        <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
          Clima en vivo
        </Chip>
        <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
          Datos de Postgres
        </Chip>
      </div>

      {errorStats && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-950/40 dark:text-red-400">{errorStats}</p>
      )}

      {objetivos.map((objetivo) => (
        <div key={objetivo.titulo} className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{objetivo.titulo}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {objetivo.kpis.map((kpi) => {
              const Icono = kpi.icon;
              return (
                <Card
                  key={kpi.label}
                  isPressable
                  onPress={() => setKpiAbierto(kpi.label)}
                  className="border border-slate-200 bg-white text-left shadow-sm dark:bg-slate-800 dark:border-slate-700"
                >
                  <CardBody className="space-y-3">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                          {kpi.label}
                          <InfoTip texto={kpi.tip} />
                        </p>
                        <p className="text-2xl font-bold">{loadingStats ? "…" : kpi.value}</p>
                      </div>
                      <Chip color={kpi.color} size="sm" className="dark:bg-slate-600 dark:text-slate-200">
                        <Icono className="h-3.5 w-3.5" />
                      </Chip>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{kpi.sub}</p>
                    <div className="flex items-center justify-between gap-2 border-t border-slate-100 pt-2 dark:border-slate-700">
                      <p className="text-xs text-slate-400 dark:text-slate-500">{kpi.meta}</p>
                      {kpi.cumplida === true && (
                        <Chip color="success" size="sm" variant="flat">Cumple meta</Chip>
                      )}
                      {kpi.cumplida === false && (
                        <Chip color="danger" size="sm" variant="flat">Por debajo de meta</Chip>
                      )}
                      {kpi.cumplida === null && (
                        <Chip color="default" size="sm" variant="flat">Seguimiento</Chip>
                      )}
                    </div>
                  </CardBody>
                </Card>
              );
            })}
          </div>
        </div>
      ))}

      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Otros indicadores operativos</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {otrosIndicadores.map((metric) => {
            const Icono = metric.icon;
            return (
              <Card key={metric.label} className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
                <CardBody className="space-y-3">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                        {metric.label}
                        <InfoTip texto={metric.tip} />
                      </p>
                      <p className="text-2xl font-bold">{loadingStats ? "…" : metric.value}</p>
                    </div>
                    <Chip color={metric.color} size="sm" className="dark:bg-slate-600 dark:text-slate-200">
                      <Icono className="h-3.5 w-3.5" />
                    </Chip>
                  </div>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{metric.sub}</p>
                </CardBody>
              </Card>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700 lg:col-span-2">
          <CardBody className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Informe del clima</p>
                <h2 className="text-2xl font-semibold">Clima actual del campo</h2>
              </div>
              <CloudRain className="w-6 h-6 text-sky-500" />
            </div>

            {sinOrtomosaico ? (
              <p className="text-slate-500 dark:text-slate-400">
                Subí un ortomosaico en "Vista de Imagen" para ver el clima de tu campo.
              </p>
            ) : loadingClima ? (
              <p className="text-slate-500 dark:text-slate-400">Cargando clima...</p>
            ) : errorClima ? (
              <p className="text-sm text-red-500">{errorClima}</p>
            ) : weather ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-700">
                  <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                    <Thermometer className="h-5 w-5" />
                    <p className="text-sm">Temperatura</p>
                  </div>
                  <p className="mt-2 text-2xl font-semibold">{weather.temperature}°C</p>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-700">
                  <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                    <Wind className="h-5 w-5" />
                    <p className="text-sm">Velocidad del viento</p>
                  </div>
                  <p className="mt-2 text-2xl font-semibold">{weather.windspeed} km/h</p>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-700">
                  <p className="text-sm text-slate-500 dark:text-slate-400">Condición</p>
                  <p className="mt-2 text-2xl font-semibold">{weatherCodeToText(weather.weathercode)}</p>
                </div>
              </div>
            ) : (
              <p className="text-slate-500 dark:text-slate-400">No hay datos de clima disponibles.</p>
            )}
          </CardBody>
        </Card>

        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <CardBody className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Siguiente paso</p>
                <h2 className="text-2xl font-semibold">Qué hacer ahora</h2>
              </div>
              <Sparkles className="w-6 h-6 text-emerald-500" />
            </div>

            <p className="text-slate-600 dark:text-slate-400">
              {sinAnalisis
                ? "Todavía no corrieron ningún análisis. Subí un ortomosaico y analizalo para ver los indicadores reales acá."
                : stats && stats.cobertura.pct_cobertura >= 20
                ? `La cobertura de malezas (${stats.cobertura.pct_cobertura}%) está por encima del 20%: conviene revisar las zonas marcadas antes de la próxima pasada de herbicida.`
                : "La cobertura de malezas está dentro de lo esperado. Seguí monitoreando con el clima actual, son buenas condiciones para un análisis nuevo."}
            </p>
            <Button
              color="primary"
              size="md"
              className="mt-4 dark:bg-blue-700 dark:text-blue-100 dark:hover:bg-blue-600"
              onPress={() => navegar("/campo")}
            >
              Ver imagen de campo
            </Button>
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <CardBody className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Confiabilidad</p>
                <h2 className="flex items-center gap-2 text-2xl font-semibold">
                  Confianza por versión de modelo
                  <InfoTip texto="Cada versión de modelo que corrió al menos un análisis con detecciones, con su confianza promedio. Cuando se active un modelo reentrenado, aparece acá como una fila nueva para comparar contra el actual." />
                </h2>
              </div>
              <Cpu className="w-6 h-6 text-indigo-500" />
            </div>

            {!stats || stats.modelo.por_version.length === 0 ? (
              <p className="text-slate-500 dark:text-slate-400">Sin corridas con detecciones todavía.</p>
            ) : (
              <div className="space-y-3">
                {stats.modelo.por_version.map((v) => (
                  <div key={v.version_modelo}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{v.version_modelo}</span>
                      <span className="text-slate-500 dark:text-slate-400">
                        {Math.round(v.confianza_promedio)}% · {v.corridas} corridas · {v.detecciones} detecciones
                      </span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700">
                      <div
                        className="h-2 rounded-full bg-indigo-500"
                        style={{ width: `${Math.min(100, Math.round(v.confianza_promedio))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <CardBody className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Rendimiento</p>
                <h2 className="flex items-center gap-2 text-2xl font-semibold">
                  Eficiencia del pipeline
                  <InfoTip texto="Cuánto tardó cada análisis completo dividido su cantidad de celdas, para las últimas 10 corridas. Sirve para notar si el tiempo de análisis se está yendo de control a medida que suben las imágenes reales." />
                </h2>
              </div>
              <Gauge className="w-6 h-6 text-rose-500" />
            </div>

            {historialEficiencia.length === 0 ? (
              <p className="text-slate-500 dark:text-slate-400">Todavía no hay análisis completos para medir tiempos.</p>
            ) : (
              <>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Promedio: <span className="font-semibold text-slate-700 dark:text-slate-200">{stats?.eficiencia.promedio_seg_por_celda}s</span> por celda, últimas {historialEficiencia.length} corridas
                </p>
                <div className="flex items-end gap-1.5 h-24">
                  {historialEficiencia.map((punto, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1" title={`${punto.seg_por_celda}s/celda`}>
                      <div
                        className="w-full rounded-t bg-rose-400 dark:bg-rose-500"
                        style={{ height: `${Math.max(6, Math.round((punto.seg_por_celda / maxSegPorCelda) * 100))}%` }}
                      />
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardBody>
        </Card>
      </div>

      <Drawer isOpen={kpiAbierto !== null} onOpenChange={(abierto) => !abierto && setKpiAbierto(null)} placement="right" size="lg" scrollBehavior="inside">
        <DrawerContent>
          {() => {
            const kpi = objetivos.flatMap((o) => o.kpis).find((k) => k.label === kpiAbierto) ?? null;
            if (!kpi) return null;
            return (
              <>
                <DrawerHeader className="flex flex-col gap-1">
                  <span>{kpi.label}</span>
                  <span className="text-sm font-normal text-slate-500 dark:text-slate-400">{kpi.descripcion}</span>
                </DrawerHeader>
                <DrawerBody className="space-y-6 pb-8">
                  <div className="flex items-center justify-center rounded-2xl bg-slate-50 p-6 dark:bg-slate-900">
                    {kpi.grafico === null ? (
                      <p className="text-sm text-slate-500 dark:text-slate-400">Todavía no hay datos suficientes para graficar este KPI.</p>
                    ) : kpi.grafico.tipo === "torta" ? (
                      <DonutKpi segmentos={kpi.grafico.segmentos} />
                    ) : (
                      <GaugeKpi value={kpi.grafico.value} meta={kpi.grafico.meta} unidad={kpi.grafico.unidad} cumplida={kpi.cumplida} />
                    )}
                  </div>

                  <dl className="divide-y divide-slate-100 text-sm dark:divide-slate-700">
                    <div className="flex justify-between gap-4 py-2">
                      <dt className="text-slate-500 dark:text-slate-400">Indicador</dt>
                      <dd className="text-right font-medium">{kpi.indicador}</dd>
                    </div>
                    <div className="flex justify-between gap-4 py-2">
                      <dt className="text-slate-500 dark:text-slate-400">Unidad de medida</dt>
                      <dd className="text-right font-medium">{kpi.unidadMedida}</dd>
                    </div>
                    <div className="flex justify-between gap-4 py-2">
                      <dt className="text-slate-500 dark:text-slate-400">Frecuencia de medición</dt>
                      <dd className="text-right font-medium">{kpi.frecuencia}</dd>
                    </div>
                    <div className="flex justify-between gap-4 py-2">
                      <dt className="text-slate-500 dark:text-slate-400">Herramienta</dt>
                      <dd className="max-w-[60%] text-right font-medium">{kpi.herramienta}</dd>
                    </div>
                    <div className="flex justify-between gap-4 py-2">
                      <dt className="text-slate-500 dark:text-slate-400">Meta</dt>
                      <dd className="max-w-[60%] text-right font-medium">{kpi.meta}</dd>
                    </div>
                  </dl>
                </DrawerBody>
              </>
            );
          }}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
