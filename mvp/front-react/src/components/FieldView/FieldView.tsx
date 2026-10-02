// =====================================
// src/components/FieldView/FieldView.tsx
// =====================================
import { useEffect, useRef, useState } from "react";
import { Card, CardBody, Chip, Button } from "@heroui/react";
import { Camera, MapPin, UploadCloud, Radar } from "lucide-react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { motion, AnimatePresence } from "framer-motion";
import {
  listarImagenes,
  obtenerMetadata,
  urlTeselas,
  subirImagen,
  analizarEnVivo,
  type ImagenMeta,
  type Deteccion,
  type ChunkAnalisis,
} from "../../services/ImagenesService";

const PALETA_CLASES = ["#34d399", "#60a5fa", "#f472b6", "#fbbf24", "#a78bfa", "#f87171", "#22d3ee", "#fb923c"];

function colorDeClase(clase: string): string {
  let hash = 0;
  for (let i = 0; i < clase.length; i++) hash = clase.charCodeAt(i) + ((hash << 5) - hash);
  return PALETA_CLASES[Math.abs(hash) % PALETA_CLASES.length];
}

/**
 * El backend ubica cada detección en el centro de la celda de 640px que la
 * contiene (no el de su propia caja), así que varias detecciones de la
 * misma celda comparten coordenada y se tapan entre sí en el mapa. Como sí
 * tenemos la caja en píxeles de la imagen completa (box_global_px) y los
 * bounds georreferenciados, reproyectamos nosotros el centro de esa caja
 * asumiendo un raster north-up sin rotación (el caso normal en un
 * ortomosaico). Da una posición mucho más precisa por detección.
 */
function pixelAGeo(xPx: number, yPx: number, meta: ImagenMeta): { lat: number; lon: number } {
  const [[sur, oeste], [norte, este]] = meta.bounds;
  const lon = oeste + (xPx / meta.ancho_px) * (este - oeste);
  const lat = norte - (yPx / meta.alto_px) * (norte - sur);
  return { lat, lon };
}

function posicionDeDeteccion(d: Deteccion, meta: ImagenMeta | null): { lat: number; lon: number } {
  if (!meta || !d.box_global_px || d.box_global_px.length < 4) return d.gps_centro;
  const [x1, y1, x2, y2] = d.box_global_px;
  return pixelAGeo((x1 + x2) / 2, (y1 + y2) / 2, meta);
}

/** Relación de aspecto (ancho/alto) de los bounds geográficos, corregida por
 * latitud (a mayor latitud, un grado de longitud mide menos en el terreno).
 * Sirve para que el contenedor del mapa tenga la misma forma que la imagen
 * en vez de un alto fijo con mucho espacio vacío alrededor. */
function aspectoDeImagen(meta: ImagenMeta | null): number {
  if (!meta) return 16 / 9;
  const [[sur, oeste], [norte, este]] = meta.bounds;
  const diffLat = norte - sur;
  if (diffLat <= 0) return 16 / 9;
  const diffLon = este - oeste;
  const correccion = Math.cos(((norte + sur) / 2) * (Math.PI / 180));
  const relacion = (diffLon * correccion) / diffLat;
  return Math.min(Math.max(relacion, 0.6), 2.4);
}

/**
 * Centra y ajusta el zoom al contenedor. No alcanza con hacerlo una sola vez
 * al montar: el contenedor usa aspect-ratio dinámico (depende del ancho, que
 * puede no estar resuelto todavía en el primer render) y además puede
 * cambiar de tamaño después (fuente que termina de cargar, resize de
 * ventana, el grid que pasa a una columna en pantallas chicas). Si eso pasa
 * y solo invalidamos el tamaño sin volver a encuadrar, el mapa queda con el
 * zoom de cuando el contenedor era de otro tamaño: mismo síntoma (hueco
 * vacío al costado) pero por timing, no siempre reproducible. Por eso acá
 * siempre van juntos: cada vez que el tamaño del contenedor cambia, se
 * invalida Y se vuelve a hacer fitBounds.
 */
function AjustarVista({ bounds }: { bounds: LatLngBoundsExpression | null }) {
  const map = useMap();
  useEffect(() => {
    if (!bounds) return;
    const contenedor = map.getContainer();
    const encuadrar = () => {
      map.invalidateSize();
      map.fitBounds(bounds);
    };
    encuadrar();
    const observer = new ResizeObserver(encuadrar);
    observer.observe(contenedor);
    return () => observer.disconnect();
  }, [bounds, map]);
  return null;
}

/** Spinner doble, para los estados "cargando" sin porcentaje conocido. */
function IndicadorCarga() {
  return (
    <div className="relative h-14 w-14">
      <span className="absolute inset-0 animate-spin rounded-full border-4 border-emerald-200 border-t-emerald-500 [animation-duration:1s] dark:border-emerald-900 dark:border-t-emerald-400" />
      <span className="absolute inset-2.5 animate-spin rounded-full border-[3px] border-transparent border-b-sky-400 [animation-direction:reverse] [animation-duration:0.7s] dark:border-b-sky-300" />
    </div>
  );
}

/** Anillo de progreso real (0-100), para cuando sí sabemos el porcentaje. */
function AnilloProgreso({ progreso }: { progreso: number }) {
  const tam = 64;
  const grosor = 6;
  const radio = (tam - grosor) / 2;
  const circunferencia = 2 * Math.PI * radio;
  const pct = Math.min(Math.max(progreso, 0), 100);
  const offset = circunferencia - (pct / 100) * circunferencia;
  return (
    <div className="relative shrink-0" style={{ width: tam, height: tam }}>
      <svg width={tam} height={tam} className="-rotate-90">
        <circle cx={tam / 2} cy={tam / 2} r={radio} strokeWidth={grosor} fill="none" className="stroke-slate-200 dark:stroke-slate-600" />
        <motion.circle
          cx={tam / 2}
          cy={tam / 2}
          r={radio}
          strokeWidth={grosor}
          fill="none"
          strokeLinecap="round"
          className="stroke-emerald-500 dark:stroke-emerald-400"
          strokeDasharray={circunferencia}
          animate={{ strokeDashoffset: offset }}
          transition={{ ease: "easeOut", duration: 0.35 }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-slate-700 dark:text-slate-100">
        {Math.round(pct)}%
      </div>
    </div>
  );
}

export default function FieldView() {
  const [imagenes, setImagenes] = useState<ImagenMeta[]>([]);
  const [imagenId, setImagenId] = useState<string | null>(null);
  const [meta, setMeta] = useState<ImagenMeta | null>(null);
  const [cargandoLista, setCargandoLista] = useState(true);
  const [cargandoMapa, setCargandoMapa] = useState(false);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);

  const [archivo, setArchivo] = useState<File | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [progresoSubida, setProgresoSubida] = useState(0);

  const [cuadrante, setCuadrante] = useState("");
  const [confianza, setConfianza] = useState(10);
  const [analizando, setAnalizando] = useState(false);
  const [progresoAnalisis, setProgresoAnalisis] = useState<ChunkAnalisis | null>(null);
  const [detecciones, setDetecciones] = useState<Deteccion[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    cargarListado();
    return () => eventSourceRef.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function cargarListado(seleccionarId?: string) {
    setCargandoLista(true);
    setErrorGeneral(null);
    try {
      const lista = await listarImagenes();
      setImagenes(lista);
      const idAUsar = seleccionarId ?? lista[0]?.id ?? null;
      if (idAUsar) await seleccionarImagen(idAUsar);
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setCargandoLista(false);
    }
  }

  async function seleccionarImagen(id: string) {
    eventSourceRef.current?.close();
    setAnalizando(false);
    setProgresoAnalisis(null);
    setDetecciones([]);
    setCargandoMapa(true);
    setImagenId(id);
    try {
      const m = await obtenerMetadata(id);
      setMeta(m);
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo cargar el ortomosaico.");
      setMeta(null);
    } finally {
      setCargandoMapa(false);
    }
  }

  async function handleSubir() {
    if (!archivo) return;
    setSubiendo(true);
    setProgresoSubida(0);
    setErrorGeneral(null);
    try {
      const nuevaMeta = await subirImagen(archivo, setProgresoSubida);
      setArchivo(null);
      await cargarListado(nuevaMeta.id);
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo subir la imagen.");
    } finally {
      setSubiendo(false);
    }
  }

  function handleAnalizar() {
    if (!imagenId) return;
    setDetecciones([]);
    setAnalizando(true);
    setProgresoAnalisis(null);
    setErrorGeneral(null);

    eventSourceRef.current = analizarEnVivo(
      imagenId,
      { cuadrante: cuadrante ? Number(cuadrante) : undefined, conf: confianza / 100 },
      (chunk) => {
        setProgresoAnalisis(chunk);
        setDetecciones((prev) => [...prev, ...chunk.detecciones]);
      },
      () => setAnalizando(false),
      () => {
        setAnalizando(false);
        setErrorGeneral("El análisis se interrumpió. Probá de nuevo.");
      }
    );
  }

  const conteoPorClase = detecciones.reduce<Record<string, number>>((acc, d) => {
    acc[d.clase] = (acc[d.clase] ?? 0) + 1;
    return acc;
  }, {});
  const claseDominante = Object.entries(conteoPorClase).sort((a, b) => b[1] - a[1])[0]?.[0];

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Vista de Imagen</h1>
          <p className="text-slate-600 dark:text-slate-400">
            Ortomosaico real del campo, con detecciones geolocalizadas en vivo.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip color="secondary" className="dark:bg-slate-600 dark:text-slate-200">
            Mapa geoespacial
          </Chip>
          <Chip color="secondary" className="dark:bg-slate-600 dark:text-slate-200">
            Análisis en vivo
          </Chip>
        </div>
      </div>

      {errorGeneral && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {errorGeneral}
        </div>
      )}

      <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
        <CardBody className="space-y-4">
          <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-600 dark:text-slate-400">
                Ortomosaico
              </label>
              <select
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-700 dark:text-slate-100"
                value={imagenId ?? ""}
                onChange={(e) => seleccionarImagen(e.target.value)}
                disabled={imagenes.length === 0}
              >
                {imagenes.length === 0 ? (
                  <option value="">Sin imágenes cargadas</option>
                ) : (
                  imagenes.map((img) => (
                    <option key={img.id} value={img.id}>
                      {img.nombre}
                    </option>
                  ))
                )}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <label className="cursor-pointer rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-600 transition-colors hover:border-emerald-400 hover:text-emerald-600 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300">
                <input
                  type="file"
                  accept=".tif,.tiff"
                  className="hidden"
                  onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                />
                <span className="flex items-center gap-2">
                  <UploadCloud className="h-4 w-4" />
                  {archivo ? archivo.name : "Elegir GeoTIFF"}
                </span>
              </label>
              <Button
                color="primary"
                isDisabled={!archivo || subiendo}
                onPress={handleSubir}
                className="dark:bg-blue-700 dark:text-blue-100 dark:hover:bg-blue-600"
              >
                {subiendo ? "Subiendo..." : "Subir"}
              </Button>
            </div>
          </div>

          {subiendo && (
            <div className="space-y-1">
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <motion.div
                  className="h-full rounded-full bg-emerald-500"
                  animate={{ width: `${progresoSubida}%` }}
                  transition={{ ease: "easeOut", duration: 0.2 }}
                />
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Subiendo y convirtiendo a COG... {progresoSubida}%
              </p>
            </div>
          )}
        </CardBody>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <CardBody className="space-y-4">
            <div
              className="relative w-full overflow-hidden rounded-3xl border border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-900"
              style={{ aspectRatio: aspectoDeImagen(meta), maxHeight: 600, minHeight: 320 }}
            >
              {!imagenId && !cargandoLista ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-500 dark:text-slate-400">
                  <Camera className="h-8 w-8" />
                  <p>Subí un ortomosaico GeoTIFF para empezar.</p>
                </div>
              ) : cargandoMapa || cargandoLista ? (
                <div className="flex h-full items-center justify-center">
                  <div className="flex flex-col items-center gap-3 text-slate-500 dark:text-slate-400">
                    <IndicadorCarga />
                    <p className="text-sm">Cargando ortomosaico...</p>
                  </div>
                </div>
              ) : (
                <MapContainer
                  key={imagenId}
                  className="h-full w-full"
                  center={[-27.08, -65.32]}
                  zoom={13}
                  minZoom={meta?.minzoom}
                  maxZoom={meta ? meta.maxzoom + 3 : undefined}
                  scrollWheelZoom
                >
                  {meta && <AjustarVista bounds={meta.bounds} />}
                  {meta && (
                    // maxNativeZoom + maxZoom extendido: si el rango de zoom del COG es más
                    // angosto que lo que hace falta para llenar el contenedor (imagen chica
                    // respecto a sus bounds), Leaflet reescala el último nivel en vez de
                    // quedarse con un hueco gris alrededor.
                    <TileLayer
                      url={urlTeselas(imagenId!)}
                      minZoom={meta.minzoom}
                      maxZoom={meta.maxzoom + 3}
                      maxNativeZoom={meta.maxzoom}
                      attribution="Ortomosaico"
                    />
                  )}
                  {detecciones.map((d, i) => {
                    const pos = posicionDeDeteccion(d, meta);
                    return (
                      <CircleMarker
                        key={`${d.fila}-${d.col}-${i}`}
                        center={[pos.lat, pos.lon]}
                        radius={5 + Math.min(d.confianza / 20, 4)}
                        color={colorDeClase(d.clase)}
                        fillColor={colorDeClase(d.clase)}
                        fillOpacity={0.85}
                        weight={2}
                        className="deteccion-marker"
                      >
                        <Popup>
                          <div className="space-y-1 text-sm">
                            <p className="font-semibold capitalize">{d.clase}</p>
                            <p>Confianza: {d.confianza.toFixed(1)}%</p>
                            <p className="text-slate-500 dark:text-slate-400">
                              {pos.lat.toFixed(5)}, {pos.lon.toFixed(5)}
                            </p>
                          </div>
                        </Popup>
                      </CircleMarker>
                    );
                  })}
                </MapContainer>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-3xl bg-slate-50 p-4 dark:bg-slate-700">
                <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                  <Camera className="h-5 w-5" />
                  <p className="text-sm">Resolución</p>
                </div>
                <p className="mt-3 text-xl font-semibold">{meta ? `${meta.ancho_px} x ${meta.alto_px}` : "—"}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4 dark:bg-slate-700">
                <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                  <MapPin className="h-5 w-5" />
                  <p className="text-sm">Ortomosaico</p>
                </div>
                <p className="mt-3 truncate text-xl font-semibold">{meta?.nombre ?? "—"}</p>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
          <CardBody className="space-y-6">
            <div className="flex items-center gap-3">
              <Radar className="h-5 w-5 text-slate-500 dark:text-slate-400" />
              <h2 className="text-xl font-semibold">Análisis en vivo</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-600 dark:text-slate-400">Zona a analizar</label>
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-700 dark:text-slate-100"
                  value={cuadrante}
                  onChange={(e) => setCuadrante(e.target.value)}
                  disabled={analizando}
                >
                  <option value="">Imagen completa</option>
                  <option value="1">Cuadrante 1 (noroeste)</option>
                  <option value="2">Cuadrante 2 (noreste)</option>
                  <option value="3">Cuadrante 3 (suroeste)</option>
                  <option value="4">Cuadrante 4 (sureste)</option>
                </select>
              </div>

              <div>
                <label className="mb-2 flex justify-between text-sm font-medium text-slate-600 dark:text-slate-400">
                  <span>Confianza mínima</span>
                  <span>{confianza}%</span>
                </label>
                <input
                  type="range"
                  min={1}
                  max={90}
                  value={confianza}
                  onChange={(e) => setConfianza(Number(e.target.value))}
                  disabled={analizando}
                  className="w-full accent-emerald-500"
                />
              </div>

              <Button
                color="primary"
                className="w-full dark:bg-blue-700 dark:text-blue-100 dark:hover:bg-blue-600"
                isDisabled={!imagenId || analizando}
                onPress={handleAnalizar}
              >
                {analizando ? "Analizando..." : "Analizar (en vivo)"}
              </Button>
            </div>

            <AnimatePresence>
              {(analizando || progresoAnalisis) && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-center gap-4 overflow-hidden rounded-2xl bg-slate-50 p-4 dark:bg-slate-700"
                >
                  <AnilloProgreso progreso={progresoAnalisis?.progreso_pct ?? 0} />
                  <div className="min-w-0 flex-1 space-y-2">
                    <span className="block font-medium text-slate-700 dark:text-slate-200">
                      {analizando ? "Procesando celdas..." : "Análisis completado"}
                    </span>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-600">
                      <motion.div
                        className="h-full rounded-full bg-emerald-500"
                        animate={{ width: `${progresoAnalisis?.progreso_pct ?? 0}%` }}
                        transition={{ ease: "easeOut", duration: 0.3 }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400">
                      <span>
                        Bloque {progresoAnalisis?.bloque ?? 0}/{progresoAnalisis?.total_bloques ?? "—"}
                      </span>
                      <span>{progresoAnalisis?.total_acumuladas ?? 0} detecciones acumuladas</span>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-3 text-slate-600 dark:text-slate-400">
              <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Resultados</p>
              {detecciones.length === 0 ? (
                <p className="text-sm">Todavía no corriste un análisis sobre este ortomosaico.</p>
              ) : (
                <>
                  <p>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">Total detectado:</span>{" "}
                    {detecciones.length}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">Clase más frecuente:</span>{" "}
                    {claseDominante}
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {Object.entries(conteoPorClase).map(([clase, cantidad]) => (
                      <Chip key={clase} size="sm" style={{ backgroundColor: `${colorDeClase(clase)}26`, color: colorDeClase(clase) }}>
                        {clase}: {cantidad}
                      </Chip>
                    ))}
                  </div>
                </>
              )}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
