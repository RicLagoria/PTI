import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardBody, Chip, Button, Tooltip } from "@heroui/react";
import { CloudRain, Thermometer, Wind, Sparkles, Leaf, Gauge, Cpu, Images, Info } from "lucide-react";
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

export default function Dashboard() {
  const navegar = useNavigate();
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [loadingClima, setLoadingClima] = useState(false);
  const [errorClima, setErrorClima] = useState<string | null>(null);
  const [sinOrtomosaico, setSinOrtomosaico] = useState(false);

  const [stats, setStats] = useState<Estadisticas | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [errorStats, setErrorStats] = useState<string | null>(null);

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

  const metrics = [
    {
      label: "Cobertura de malezas",
      value: sinAnalisis ? "—" : `${stats?.cobertura.pct_cobertura ?? 0}%`,
      sub: "Celdas con maleza / celdas inspeccionadas, último análisis de cada imagen",
      tip: "De cada ortomosaico se toma solo su análisis completo más reciente (no se suman corridas repetidas). Es el % de esas celdas donde se detectó al menos una maleza.",
      icon: Leaf,
      color: "success" as const,
    },
    {
      label: "Maleza principal",
      value: sinAnalisis || !stats?.cobertura.clase_principal ? "—" : (CLASE_LABEL[stats.cobertura.clase_principal] ?? stats.cobertura.clase_principal),
      sub: sinAnalisis ? "Todavía no hay análisis corridos" : `${stats?.cobertura.detecciones_totales ?? 0} detecciones en total`,
      tip: "La clase con más detecciones acumuladas, contando el último análisis completo de cada imagen.",
      icon: Sparkles,
      color: "warning" as const,
    },
    {
      label: "Confianza del modelo",
      value: modeloReciente ? `${Math.round(modeloReciente.confianza_promedio * 100)}%` : "—",
      sub: modeloReciente ? `Versión ${modeloReciente.version_modelo} · ${modeloReciente.corridas} corridas` : "Sin corridas con detecciones aún",
      tip: "Promedio de confianza de todas las detecciones hechas con la versión de modelo que corrió más recientemente. Si no hubo detecciones todavía, no hay nada para promediar.",
      icon: Cpu,
      color: "primary" as const,
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
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-slate-600 dark:text-slate-400">Estado real del análisis de malezas del equipo y clima actual del campo.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
            Clima en vivo
          </Chip>
          <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
            Datos de Postgres
          </Chip>
        </div>
      </div>

      {errorStats && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-950/40 dark:text-red-400">{errorStats}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
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
                        {Math.round(v.confianza_promedio * 100)}% · {v.corridas} corridas · {v.detecciones} detecciones
                      </span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-slate-100 dark:bg-slate-700">
                      <div
                        className="h-2 rounded-full bg-indigo-500"
                        style={{ width: `${Math.min(100, Math.round(v.confianza_promedio * 100))}%` }}
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
    </div>
  );
}
