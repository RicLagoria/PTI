// =====================================
// src/components/graficos/GraficoLineas.tsx
// =====================================
// Gráfico de líneas en SVG: una sola escala Y, línea de 2px, línea de referencia
// que se ajusta al punto más cercano con un tooltip que lista todas las series,
// y una vista en tabla para quien no puede o no quiere leer el gráfico.
import { useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { useAncho } from "../../hooks/useAncho";

export interface Serie {
  clave: string;
  nombre: string;
  /** Variable CSS de la paleta categórica, en orden fijo: var(--serie-1), var(--serie-2)… */
  color: string;
  valores: (number | null)[];
}

interface Props {
  /** Describe el gráfico para lectores de pantalla */
  titulo: string;
  x: number[];
  series: Serie[];
  etiquetaX: string;
  formatoX: (valor: number) => string;
  formatoY: (valor: number) => string;
  /** Si no se pasa, va de 0 al máximo de los datos redondeado */
  dominioY?: [number, number];
  /** Línea vertical de referencia, por ejemplo el umbral recomendado */
  marcador?: { x: number; etiqueta: string };
  alto?: number;
}

const ARRIBA = 16;
const ABAJO = 34;
const IZQUIERDA = 48;

/** Marcas del eje Y en números redondos (0, 0,25, 0,5…) que cubren el máximo. */
function marcasLimpias(maximo: number, cantidad = 4): number[] {
  if (!(maximo > 0)) return [0, 1];
  const pasoCrudo = maximo / cantidad;
  const potencia = 10 ** Math.floor(Math.log10(pasoCrudo));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= pasoCrudo - 1e-12) ?? pasoCrudo;
  const marcas: number[] = [];
  for (let v = 0; v < maximo + paso - 1e-9; v += paso) marcas.push(Number(v.toFixed(10)));
  return marcas;
}

/** Marcas en números redondos dentro de [minimo, maximo] (0, 25, 50… o 10, 20, 30…). */
function marcasEnRango(minimo: number, maximo: number, cantidad = 4): number[] {
  if (!(maximo > minimo)) return [minimo];
  const pasoCrudo = (maximo - minimo) / cantidad;
  const potencia = 10 ** Math.floor(Math.log10(pasoCrudo));
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= pasoCrudo - 1e-12) ?? pasoCrudo;
  const marcas: number[] = [];
  for (let v = Math.ceil(minimo / paso - 1e-9) * paso; v <= maximo + 1e-9; v += paso) marcas.push(Number(v.toFixed(10)));
  return marcas;
}

function trazo(xs: number[], ys: (number | null)[]): string {
  let d = "";
  let abierto = false;
  ys.forEach((y, i) => {
    if (y === null) {
      abierto = false;
      return;
    }
    d += `${abierto ? "L" : "M"}${xs[i].toFixed(1)},${y.toFixed(1)}`;
    abierto = true;
  });
  return d;
}

export default function GraficoLineas({ titulo, x, series, etiquetaX, formatoX, formatoY, dominioY, marcador, alto = 220 }: Props) {
  const [contenedor, ancho] = useAncho<HTMLDivElement>();
  const [indice, setIndice] = useState<number | null>(null);

  const conEtiquetas = series.length >= 2 && series.length <= 4;
  const derecha = conEtiquetas ? 76 : 16;
  const anchoUtil = Math.max(10, ancho - IZQUIERDA - derecha);
  const altoUtil = alto - ARRIBA - ABAJO;

  const maximoDatos = Math.max(0, ...series.flatMap((s) => s.valores.filter((v): v is number => v !== null)));
  const marcasY = dominioY ? marcasLimpias(dominioY[1]) : marcasLimpias(maximoDatos);
  const [yMin, yMax] = dominioY ?? [0, marcasY[marcasY.length - 1]];
  const xMin = x[0] ?? 0;
  const xMax = x[x.length - 1] ?? 1;

  const escalaX = (v: number) => IZQUIERDA + (xMax === xMin ? 0 : ((v - xMin) / (xMax - xMin)) * anchoUtil);
  const escalaY = (v: number) => ARRIBA + altoUtil - ((v - yMin) / (yMax - yMin || 1)) * altoUtil;
  const xs = x.map(escalaX);

  const marcasX = x.length <= 6 ? x : marcasEnRango(xMin, xMax);

  // Etiquetas al final de cada línea; si quedan encimadas no se apilan: se deja la leyenda y el tooltip
  const finales = series
    .map((s) => {
      const i = s.valores.map((v, j) => (v === null ? -1 : j)).filter((j) => j >= 0).pop();
      return i === undefined ? null : { serie: s, y: escalaY(s.valores[i] as number) };
    })
    .filter((f): f is { serie: Serie; y: number } => f !== null)
    .sort((a, b) => a.y - b.y);
  const etiquetasVisibles = conEtiquetas && finales.every((f, i) => i === 0 || f.y - finales[i - 1].y >= 14);

  const alMover = (e: PointerEvent<SVGRectElement>) => {
    const caja = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const px = e.clientX - caja.left;
    let mejor = 0;
    xs.forEach((v, i) => {
      if (Math.abs(v - px) < Math.abs(xs[mejor] - px)) mejor = i;
    });
    setIndice(mejor);
  };

  const alTeclear = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const actual = indice ?? x.length - 1;
    setIndice(Math.min(x.length - 1, Math.max(0, actual + (e.key === "ArrowRight" ? 1 : -1))));
  };

  const xTooltip = indice !== null ? xs[indice] : 0;
  const tooltipALaIzquierda = xTooltip > IZQUIERDA + anchoUtil * 0.6;

  return (
    <div className="space-y-2">
      {series.length >= 2 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300" aria-label="Leyenda">
          {series.map((s) => (
            <li key={s.clave} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-4 rounded-full" style={{ background: s.color }} />
              {s.nombre}
            </li>
          ))}
        </ul>
      )}

      <div ref={contenedor} className="relative">
        <svg
          width={ancho}
          height={alto}
          role="img"
          aria-label={`${titulo}. Usá las flechas izquierda y derecha para recorrer los valores.`}
          tabIndex={0}
          onKeyDown={alTeclear}
          onFocus={() => setIndice((i) => i ?? x.length - 1)}
          onBlur={() => setIndice(null)}
          className="block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {marcasY.map((v) => (
            <g key={v}>
              <line x1={IZQUIERDA} x2={IZQUIERDA + anchoUtil} y1={escalaY(v)} y2={escalaY(v)} stroke={v === yMin ? "var(--grafico-eje)" : "var(--grafico-grilla)"} strokeWidth={1} />
              <text x={IZQUIERDA - 8} y={escalaY(v)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--grafico-texto)" style={{ fontVariantNumeric: "tabular-nums" }}>
                {formatoY(v)}
              </text>
            </g>
          ))}
          {marcasX.map((v) => (
            <text key={v} x={escalaX(v)} y={ARRIBA + altoUtil + 16} textAnchor="middle" fontSize={11} fill="var(--grafico-texto)" style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatoX(v)}
            </text>
          ))}
          <text x={IZQUIERDA + anchoUtil / 2} y={alto - 2} textAnchor="middle" fontSize={11} fill="var(--grafico-texto)">
            {etiquetaX}
          </text>

          {marcador && (
            <g>
              <line x1={escalaX(marcador.x)} x2={escalaX(marcador.x)} y1={ARRIBA} y2={ARRIBA + altoUtil} stroke="var(--grafico-marcador)" strokeWidth={1} />
              <text x={escalaX(marcador.x)} y={ARRIBA - 4} textAnchor={escalaX(marcador.x) > IZQUIERDA + anchoUtil * 0.8 ? "end" : "middle"} fontSize={11} fill="var(--grafico-texto)">
                {marcador.etiqueta}
              </text>
            </g>
          )}

          {series.map((s) => (
            <path key={s.clave} d={trazo(xs, s.valores.map((v) => (v === null ? null : escalaY(v))))} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          ))}

          {etiquetasVisibles &&
            finales.map((f) => (
              <text key={f.serie.clave} x={IZQUIERDA + anchoUtil + 6} y={f.y} dy="0.32em" fontSize={11} fill="var(--grafico-texto)">
                {f.serie.nombre}
              </text>
            ))}

          {indice !== null && (
            <g pointerEvents="none">
              <line x1={xTooltip} x2={xTooltip} y1={ARRIBA} y2={ARRIBA + altoUtil} stroke="var(--grafico-marcador)" strokeWidth={1} />
              {series.map((s) =>
                s.valores[indice] === null ? null : (
                  <circle key={s.clave} cx={xTooltip} cy={escalaY(s.valores[indice] as number)} r={4} fill={s.color} stroke="var(--grafico-superficie)" strokeWidth={2} />
                )
              )}
            </g>
          )}

          {/* Zona de captura: todo el área del gráfico, no solo las líneas */}
          <rect x={IZQUIERDA} y={ARRIBA} width={anchoUtil} height={altoUtil} fill="transparent" onPointerMove={alMover} onPointerLeave={() => setIndice(null)} />
        </svg>

        {indice !== null && (
          <div
            className="pointer-events-none absolute z-10 min-w-36 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg dark:border-slate-600 dark:bg-slate-900"
            style={{ top: ARRIBA, left: tooltipALaIzquierda ? undefined : xTooltip + 12, right: tooltipALaIzquierda ? ancho - xTooltip + 12 : undefined }}
            role="status"
          >
            <p className="mb-1 text-slate-500 dark:text-slate-400">
              {etiquetaX} {formatoX(x[indice])}
            </p>
            {series.map((s) => (
              <p key={s.clave} className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: s.color }} />
                <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                  {s.valores[indice] === null ? "—" : formatoY(s.valores[indice] as number)}
                </span>
                <span className="text-slate-500 dark:text-slate-400">{s.nombre}</span>
              </p>
            ))}
          </div>
        )}
      </div>

      <details className="text-xs">
        <summary className="cursor-pointer text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200">Ver como tabla</summary>
        <div className="mt-2 max-h-60 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700">
          <table className="w-full text-right tabular-nums">
            <thead className="sticky top-0 bg-slate-50 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              <tr>
                <th className="px-3 py-1.5 font-medium">{etiquetaX}</th>
                {series.map((s) => (
                  <th key={s.clave} className="px-3 py-1.5 font-medium">{s.nombre}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {x.map((v, i) => (
                <tr key={i} className="border-t border-slate-100 dark:border-slate-700/60">
                  <td className="px-3 py-1">{formatoX(v)}</td>
                  {series.map((s) => (
                    <td key={s.clave} className="px-3 py-1">{s.valores[i] === null ? "—" : formatoY(s.valores[i] as number)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
