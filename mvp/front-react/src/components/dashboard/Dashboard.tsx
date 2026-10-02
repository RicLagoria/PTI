import { useEffect, useState } from "react";
import { Card, CardBody, Chip, Button } from "@heroui/react";
import { CloudRain, Thermometer, Wind, Sparkles } from "lucide-react";
import { fetchCurrentWeather, type WeatherResponse } from "../../services/WeatherService";
import { listarImagenes } from "../../services/ImagenesService";

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

export default function Dashboard() {
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sinOrtomosaico, setSinOrtomosaico] = useState(false);

  const metrics = [
    {
      label: "Cobertura de malezas",
      value: "18%",
      color: "emerald",
    },
    {
      label: "Zonas afectadas",
      value: "3",
      color: "amber",
    },
    {
      label: "Salud del cultivo",
      value: "82%",
      color: "sky",
    },
    {
      label: "Maleza principal",
      value: "Solanacea",
      color: "lime",
    },
  ];

  useEffect(() => {
    const loadWeather = async () => {
      setLoading(true);
      setError(null);

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
        setError("No se pudo cargar el clima. Revisá tu conexión o la API.");
      } finally {
        setLoading(false);
      }
    };

    loadWeather();
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-slate-600 dark:text-slate-400">Estado inicial del análisis de malezas y clima actual del campo.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
            Clima en vivo
          </Chip>
          <Chip color="secondary" size="sm" className="dark:bg-slate-600 dark:text-slate-200">
            API abierta
          </Chip>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.label} className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
            <CardBody className="space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{metric.label}</p>
                  <p className="text-2xl font-bold">{metric.value}</p>
                </div>
                <Chip color={metric.color as any} size="sm" className="dark:bg-slate-600 dark:text-slate-200">
                  Campo
                </Chip>
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400">Métrica inicial obtenida del último análisis de la imagen.</p>
            </CardBody>
          </Card>
        ))}
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
            ) : loading ? (
              <p className="text-slate-500 dark:text-slate-400">Cargando clima...</p>
            ) : error ? (
              <p className="text-sm text-red-500">{error}</p>
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
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Sugerencia</p>
                <h2 className="text-2xl font-semibold">Próxima acción</h2>
              </div>
              <Sparkles className="w-6 h-6 text-emerald-500" />
            </div>

            <p className="text-slate-600 dark:text-slate-400">Se recomienda revisar las zonas del sector norte antes de programar aplicación de herbicida. El clima actual sugiere buenas condiciones para el análisis.</p>
            <Button color="primary" size="md" className="mt-4 dark:bg-blue-700 dark:text-blue-100 dark:hover:bg-blue-600">
              Ver imagen de campo
            </Button>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
