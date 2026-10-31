// =====================================
// src/components/FieldView/FieldView.tsx
// =====================================
import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardBody,
  Chip,
  Button,
  Tabs,
  Tab,
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerBody,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from "@heroui/react";
import { Camera, MapPin, UploadCloud, Radar, History, FileJson, FileSpreadsheet, FileText, Eye, User, ScanSearch, MoreVertical, Download } from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { motion, AnimatePresence } from "framer-motion";
import {
  listarImagenes,
  obtenerMetadata,
  urlTeselas,
  subirImagen,
  analizarEnVivo,
  listarHistorialAnalisis,
  obtenerAnalisisPasado,
  urlExportarGeoJSON,
  urlExportarCSV,
  urlExportarPDF,
  obtenerTextoExportado,
  obtenerPdfBlob,
  type ImagenMeta,
  type Deteccion,
  type ChunkAnalisis,
  type AnalisisHistorial,
  type AnalisisDetalle,
} from "../../services/ImagenesService";

const PALETA_CLASES = ["#34d399", "#60a5fa", "#f472b6", "#fbbf24", "#a78bfa", "#f87171", "#22d3ee", "#fb923c"];
const ALTO_MAX_MAPA = 560;

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
 * latitud (a mayor latitud, un grado de longitud mide menos en el terreno). */
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

/** Ícono custom con un pulso tipo radar — nada de los círculos lisos de antes. */
function iconoDeteccion(clase: string, confianza: number): L.DivIcon {
  const color = colorDeClase(clase);
  const nucleo = Math.round(10 + (Math.min(Math.max(confianza, 0), 100) / 100) * 8); // 10-18px
  const total = nucleo + 20;
  return L.divIcon({
    className: "",
    html: `<span class="marcador-deteccion" style="--color:${color};--nucleo:${nucleo}px">
      <span class="marcador-halo"></span>
      <span class="marcador-nucleo"></span>
    </span>`,
    iconSize: [total, total],
    iconAnchor: [total / 2, total / 2],
  });
}

/**
 * Centra y ajusta el zoom al contenedor. No alcanza con hacerlo una sola vez
 * al montar: el contenedor puede no tener su tamaño final resuelto todavía
 * en ese momento (fuentes, breakpoints del grid) y además puede cambiar de
 * tamaño después (resize de ventana, apertura de un drawer). Si eso pasa y
 * solo invalidamos el tamaño sin volver a encuadrar, el mapa queda con el
 * zoom de cuando el contenedor era de otro tamaño. Por eso acá siempre van
 * juntos: cada vez que el tamaño del contenedor cambia, se invalida Y se
 * vuelve a encuadrar.
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

function desglosePorClase(detecciones: Deteccion[]) {
  const conteo = detecciones.reduce<Record<string, number>>((acc, d) => {
    acc[d.clase] = (acc[d.clase] ?? 0) + 1;
    return acc;
  }, {});
  return Object.entries(conteo).sort((a, b) => b[1] - a[1]);
}

const ESTADO_ESTILO: Record<string, string> = {
  completo: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  error: "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300",
  en_progreso: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
};

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

  const [historial, setHistorial] = useState<AnalisisHistorial[]>([]);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);

  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [cargandoDrawer, setCargandoDrawer] = useState(false);
  const [analisisDrawer, setAnalisisDrawer] = useState<AnalisisDetalle | null>(null);

  const [previewAbierto, setPreviewAbierto] = useState(false);
  const [previewTipo, setPreviewTipo] = useState<"pdf" | "geojson" | "csv" | null>(null);
  const [previewAnalisisId, setPreviewAnalisisId] = useState<number | null>(null);
  const [cargandoPreview, setCargandoPreview] = useState(false);
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const [previewTexto, setPreviewTexto] = useState<string | null>(null);
  const [previewFilasCsv, setPreviewFilasCsv] = useState<string[][] | null>(null);
  const pdfUrlRef = useRef<string | null>(null);

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
    cargarHistorial(id);
  }

  async function cargarHistorial(id: string) {
    setCargandoHistorial(true);
    try {
      setHistorial(await listarHistorialAnalisis(id));
    } catch {
      setHistorial([]);
    } finally {
      setCargandoHistorial(false);
    }
  }

  async function abrirDrawer(analisisId: number) {
    if (!imagenId) return;
    setDrawerAbierto(true);
    setCargandoDrawer(true);
    setAnalisisDrawer(null);
    try {
      setAnalisisDrawer(await obtenerAnalisisPasado(imagenId, analisisId));
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo cargar ese análisis.");
      setDrawerAbierto(false);
    } finally {
      setCargandoDrawer(false);
    }
  }

  function limpiarPreview() {
    if (pdfUrlRef.current) {
      URL.revokeObjectURL(pdfUrlRef.current);
      pdfUrlRef.current = null;
    }
    setPreviewPdfUrl(null);
    setPreviewTexto(null);
    setPreviewFilasCsv(null);
  }

  async function abrirPreview(analisisId: number, tipo: "pdf" | "geojson" | "csv") {
    if (!imagenId) return;
    limpiarPreview();
    setPreviewTipo(tipo);
    setPreviewAnalisisId(analisisId);
    setPreviewAbierto(true);
    setCargandoPreview(true);
    try {
      if (tipo === "pdf") {
        const blob = await obtenerPdfBlob(imagenId, analisisId);
        const url = URL.createObjectURL(blob);
        pdfUrlRef.current = url;
        setPreviewPdfUrl(url);
      } else if (tipo === "csv") {
        const texto = await obtenerTextoExportado(imagenId, analisisId, "csv");
        setPreviewFilasCsv(texto.trim().split("\n").map((fila) => fila.split(",")));
      } else {
        const texto = await obtenerTextoExportado(imagenId, analisisId, "geojson");
        setPreviewTexto(JSON.stringify(JSON.parse(texto), null, 2));
      }
    } catch (err) {
      setErrorGeneral(err instanceof Error ? err.message : "No se pudo generar la vista previa.");
      setPreviewAbierto(false);
    } finally {
      setCargandoPreview(false);
    }
  }

  useEffect(() => () => limpiarPreview(), []);

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
      () => {
        setAnalizando(false);
        cargarHistorial(imagenId);
      },
      () => {
        setAnalizando(false);
        setErrorGeneral("El análisis se interrumpió. Probá de nuevo.");
        cargarHistorial(imagenId);
      }
    );
  }

  const clasesOrdenadas = desglosePorClase(detecciones);
  const claseDominante = clasesOrdenadas[0]?.[0];
  const aspecto = aspectoDeImagen(meta);

  const clasesDrawer = desglosePorClase(analisisDrawer?.detecciones ?? []);

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
                      {img.usuario_nombre ? ` · subida por ${img.usuario_nombre}` : ""}
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

      <Tabs aria-label="Secciones de la vista de imagen" color="primary" variant="underlined" size="lg">
        <Tab
          key="analizar"
          title={
            <span className="flex items-center gap-2">
              <ScanSearch className="h-4 w-4" />
              Analizar
            </span>
          }
        >
          <div className="grid gap-4 pt-4 xl:grid-cols-[1.4fr_1fr]">
            <Card className="border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
              <CardBody className="space-y-4">
                <div
                  className="relative mx-auto w-full overflow-hidden rounded-3xl border border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-900"
                  style={{
                    aspectRatio: aspecto,
                    maxWidth: `${Math.round(ALTO_MAX_MAPA * aspecto)}px`,
                    maxHeight: ALTO_MAX_MAPA,
                    minHeight: 240,
                  }}
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
                    <>
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
                            <Marker key={`${d.fila}-${d.col}-${i}`} position={[pos.lat, pos.lon]} icon={iconoDeteccion(d.clase, d.confianza)}>
                              <Popup>
                                <div className="w-44 space-y-2 py-0.5">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="flex items-center gap-1.5 text-sm font-semibold capitalize">
                                      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colorDeClase(d.clase) }} />
                                      {d.clase}
                                    </span>
                                    <span className="shrink-0 text-xs font-medium text-slate-400">{d.confianza.toFixed(0)}%</span>
                                  </div>
                                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-600">
                                    <div
                                      className="h-full rounded-full"
                                      style={{ width: `${d.confianza}%`, background: colorDeClase(d.clase) }}
                                    />
                                  </div>
                                  <p className="font-mono text-[11px] text-slate-400">
                                    {pos.lat.toFixed(5)}, {pos.lon.toFixed(5)}
                                  </p>
                                </div>
                              </Popup>
                            </Marker>
                          );
                        })}
                      </MapContainer>

                      {clasesOrdenadas.length > 0 && (
                        <div className="pointer-events-none absolute bottom-3 right-3 z-[1000] max-w-[10.5rem] rounded-xl bg-white/90 p-3 text-xs shadow-lg backdrop-blur-sm dark:bg-slate-800/90">
                          <p className="mb-1.5 font-semibold text-slate-700 dark:text-slate-200">Detecciones</p>
                          <div className="space-y-1">
                            {clasesOrdenadas.map(([clase, cantidad]) => (
                              <div key={clase} className="flex items-center gap-2">
                                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colorDeClase(clase) }} />
                                <span className="truncate capitalize text-slate-600 dark:text-slate-300">{clase}</span>
                                <span className="ml-auto shrink-0 font-medium text-slate-400">{cantidad}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
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
                  <div className="rounded-3xl bg-slate-50 p-4 dark:bg-slate-700">
                    <div className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                      <User className="h-5 w-5" />
                      <p className="text-sm">Subida por</p>
                    </div>
                    <p className="mt-3 truncate text-xl font-semibold">{meta?.usuario_nombre ?? "—"}</p>
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

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Resultados</p>
                    {detecciones.length > 0 && (
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{detecciones.length} en total</span>
                    )}
                  </div>

                  {detecciones.length === 0 ? (
                    <p className="text-sm text-slate-600 dark:text-slate-400">Todavía no corriste un análisis sobre este ortomosaico.</p>
                  ) : (
                    <div className="space-y-3">
                      {claseDominante && (
                        <p className="text-sm text-slate-600 dark:text-slate-400">
                          <span className="font-semibold text-slate-900 dark:text-slate-100">Más frecuente:</span>{" "}
                          <span className="capitalize">{claseDominante}</span>
                        </p>
                      )}
                      {clasesOrdenadas.map(([clase, cantidad]) => {
                        const pct = (cantidad / detecciones.length) * 100;
                        const color = colorDeClase(clase);
                        return (
                          <div key={clase} className="space-y-1">
                            <div className="flex items-center justify-between text-sm">
                              <span className="flex items-center gap-2 capitalize text-slate-700 dark:text-slate-200">
                                <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
                                {clase}
                              </span>
                              <span className="text-xs text-slate-400">
                                {cantidad} · {pct.toFixed(0)}%
                              </span>
                            </div>
                            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-600">
                              <motion.div
                                className="h-full rounded-full"
                                style={{ background: color }}
                                initial={{ width: 0 }}
                                animate={{ width: `${pct}%` }}
                                transition={{ duration: 0.5, ease: "easeOut" }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </CardBody>
            </Card>
          </div>
        </Tab>

        <Tab
          key="historial"
          title={
            <span className="flex items-center gap-2">
              <History className="h-4 w-4" />
              Historial
              {historial.length > 0 && (
                <Chip size="sm" color="secondary" className="dark:bg-slate-600 dark:text-slate-200">
                  {historial.length}
                </Chip>
              )}
            </span>
          }
        >
          <Card className="mt-4 border border-slate-200 bg-white shadow-sm dark:bg-slate-800 dark:border-slate-700">
            <CardBody className="space-y-4">
              {cargandoHistorial ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">Cargando historial...</p>
              ) : historial.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Todavía no se corrió ningún análisis sobre esta imagen.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-slate-500 dark:border-slate-700 dark:text-slate-400">
                        <th className="py-2 pr-3 font-medium">Fecha</th>
                        <th className="py-2 pr-3 font-medium">Modelo</th>
                        <th className="py-2 pr-3 font-medium">Corrido por</th>
                        <th className="py-2 pr-3 font-medium">Detecciones</th>
                        <th className="py-2 pr-3 font-medium">Estado</th>
                        <th className="py-2 pr-3 font-medium text-right">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historial.map((h) => (
                        <tr key={h.id} className="border-b border-slate-100 last:border-0 dark:border-slate-700/60">
                          <td className="py-2 pr-3 whitespace-nowrap">
                            {new Date(h.fecha_inicio).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                          </td>
                          <td className="py-2 pr-3">
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium dark:bg-slate-700">{h.version_modelo}</span>
                          </td>
                          <td className="py-2 pr-3 text-slate-600 dark:text-slate-300">{h.usuario_nombre ?? "—"}</td>
                          <td className="py-2 pr-3">{h.total_detecciones}</td>
                          <td className="py-2 pr-3">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ESTADO_ESTILO[h.estado] ?? ESTADO_ESTILO.en_progreso}`}>
                              {h.estado}
                            </span>
                          </td>
                          <td className="py-2 pr-0 text-right">
                            <Dropdown placement="bottom-end">
                              <DropdownTrigger>
                                <Button isIconOnly size="sm" variant="flat" aria-label="Acciones">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </DropdownTrigger>
                              <DropdownMenu aria-label="Acciones del análisis" disabledKeys={h.total_detecciones === 0 ? ["geojson", "csv", "pdf"] : []}>
                                <DropdownItem key="ver" startContent={<Eye className="h-4 w-4" />} onPress={() => abrirDrawer(h.id)}>
                                  Ver en el mapa
                                </DropdownItem>
                                <DropdownItem key="geojson" startContent={<FileJson className="h-4 w-4" />} onPress={() => abrirPreview(h.id, "geojson")}>
                                  Exportar GeoJSON
                                </DropdownItem>
                                <DropdownItem key="csv" startContent={<FileSpreadsheet className="h-4 w-4" />} onPress={() => abrirPreview(h.id, "csv")}>
                                  Exportar CSV
                                </DropdownItem>
                                <DropdownItem key="pdf" startContent={<FileText className="h-4 w-4" />} onPress={() => abrirPreview(h.id, "pdf")}>
                                  Ver informe PDF
                                </DropdownItem>
                              </DropdownMenu>
                            </Dropdown>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
        </Tab>
      </Tabs>

      {/* "Ver" abre esto en vez de cargar el análisis viejo en el mapa principal:
          así no se confunde con una corrida en vivo y queda su propio mapa chico. */}
      <Drawer isOpen={drawerAbierto} onOpenChange={setDrawerAbierto} placement="right" size="4xl" scrollBehavior="inside">
        <DrawerContent>
          {() => (
            <>
              <DrawerHeader className="flex flex-col gap-1">
                <span>Análisis #{analisisDrawer?.id ?? "…"}</span>
                {analisisDrawer && (
                  <span className="text-sm font-normal text-slate-500 dark:text-slate-400">
                    {new Date(analisisDrawer.fecha_inicio).toLocaleString("es-AR", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </DrawerHeader>
              <DrawerBody className="space-y-3 pb-6">
                {cargandoDrawer || !analisisDrawer ? (
                  <div className="flex h-64 items-center justify-center">
                    <IndicadorCarga />
                  </div>
                ) : (
                  <>
                    <div
                      className="relative w-full overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 dark:border-slate-700 dark:bg-slate-900"
                      style={{ aspectRatio: aspecto, minHeight: 420, maxHeight: "62vh" }}
                    >
                      <MapContainer
                        key={analisisDrawer.id}
                        className="h-full w-full"
                        center={[-27.08, -65.32]}
                        zoom={13}
                        minZoom={meta?.minzoom}
                        maxZoom={meta ? meta.maxzoom + 3 : undefined}
                        scrollWheelZoom
                      >
                        {meta && <AjustarVista bounds={meta.bounds} />}
                        {meta && imagenId && (
                          <TileLayer
                            url={urlTeselas(imagenId)}
                            minZoom={meta.minzoom}
                            maxZoom={meta.maxzoom + 3}
                            maxNativeZoom={meta.maxzoom}
                            attribution="Ortomosaico"
                          />
                        )}
                        {analisisDrawer.detecciones.map((d, i) => {
                          const pos = posicionDeDeteccion(d, meta);
                          return (
                            <Marker key={`${d.fila}-${d.col}-${i}`} position={[pos.lat, pos.lon]} icon={iconoDeteccion(d.clase, d.confianza)}>
                              <Popup>
                                <div className="w-40 space-y-1 py-0.5 text-xs">
                                  <span className="font-semibold capitalize">{d.clase}</span> · {d.confianza.toFixed(0)}%
                                </div>
                              </Popup>
                            </Marker>
                          );
                        })}
                      </MapContainer>
                    </div>

                    {/* Franja compacta en vez de 6 tarjetas: el mapa es lo que importa acá. */}
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-xl bg-slate-50 px-4 py-2.5 text-xs text-slate-500 dark:bg-slate-700/60 dark:text-slate-400">
                      <span>Modelo <strong className="text-slate-700 dark:text-slate-200">{analisisDrawer.version_modelo}</strong></span>
                      <span>Confianza mín. <strong className="text-slate-700 dark:text-slate-200">{Math.round(analisisDrawer.conf_umbral * 100)}%</strong></span>
                      <span>Corrido por <strong className="text-slate-700 dark:text-slate-200">{analisisDrawer.usuario_nombre ?? "—"}</strong></span>
                      <span>Celdas <strong className="text-slate-700 dark:text-slate-200">{analisisDrawer.celdas_activas ?? 0}/{analisisDrawer.total_celdas}</strong></span>
                      <span>Detecciones <strong className="text-slate-700 dark:text-slate-200">{analisisDrawer.detecciones.length}</strong></span>
                      <span className={`rounded-full px-2 py-0.5 font-medium ${ESTADO_ESTILO[analisisDrawer.estado] ?? ESTADO_ESTILO.en_progreso}`}>
                        {analisisDrawer.estado}
                      </span>
                    </div>

                    {clasesDrawer.length > 0 && (
                      <div className="flex flex-wrap gap-3">
                        {clasesDrawer.map(([clase, cantidad]) => {
                          const pct = (cantidad / analisisDrawer.detecciones.length) * 100;
                          const color = colorDeClase(clase);
                          return (
                            <span key={clase} className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs dark:bg-slate-700">
                              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
                              <span className="capitalize text-slate-700 dark:text-slate-200">{clase}</span>
                              <span className="text-slate-400">{cantidad} · {pct.toFixed(0)}%</span>
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}
              </DrawerBody>
            </>
          )}
        </DrawerContent>
      </Drawer>

      {/* Vista previa de lo que se exporta: GeoJSON/CSV como texto, PDF embebido
          en un iframe (los navegadores ya lo saben renderizar solos). */}
      <Drawer isOpen={previewAbierto} onOpenChange={(abierto) => { setPreviewAbierto(abierto); if (!abierto) limpiarPreview(); }} placement="right" size={previewTipo === "pdf" ? "3xl" : "lg"} scrollBehavior="inside">
        <DrawerContent>
          {() => (
            <>
              <DrawerHeader>
                {previewTipo === "pdf" ? "Informe PDF" : previewTipo === "csv" ? "Exportar CSV" : "Exportar GeoJSON"}
              </DrawerHeader>
              <DrawerBody className="pb-6">
                {cargandoPreview ? (
                  <div className="flex h-64 items-center justify-center">
                    <IndicadorCarga />
                  </div>
                ) : previewTipo === "pdf" && previewPdfUrl ? (
                  <iframe title="Informe PDF" src={previewPdfUrl} className="h-[75vh] w-full rounded-xl border border-slate-200 dark:border-slate-700" />
                ) : previewTipo === "csv" && previewFilasCsv ? (
                  <div className="overflow-auto rounded-xl border border-slate-200 dark:border-slate-700">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-slate-50 dark:bg-slate-700">
                          {previewFilasCsv[0].map((col, i) => (
                            <th key={i} className="whitespace-nowrap px-3 py-2 text-left font-medium text-slate-500 dark:text-slate-300">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewFilasCsv.slice(1).map((fila, i) => (
                          <tr key={i} className="border-t border-slate-100 dark:border-slate-700/60">
                            {fila.map((celda, j) => (
                              <td key={j} className="whitespace-nowrap px-3 py-1.5 font-mono text-slate-600 dark:text-slate-300">{celda}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : previewTexto ? (
                  <pre className="max-h-[70vh] overflow-auto rounded-xl bg-slate-50 p-4 text-xs text-slate-700 dark:bg-slate-900 dark:text-slate-300">{previewTexto}</pre>
                ) : null}

                {imagenId && previewTipo && previewAnalisisId && (
                  <Button
                    variant="flat"
                    color="primary"
                    startContent={<Download className="h-4 w-4" />}
                    as="a"
                    href={
                      previewTipo === "pdf"
                        ? urlExportarPDF(imagenId, previewAnalisisId)
                        : previewTipo === "csv"
                        ? urlExportarCSV(imagenId, previewAnalisisId)
                        : urlExportarGeoJSON(imagenId, previewAnalisisId)
                    }
                    className="mt-3"
                  >
                    Descargar archivo
                  </Button>
                )}
              </DrawerBody>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
