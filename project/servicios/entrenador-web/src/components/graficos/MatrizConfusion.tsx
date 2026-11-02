// =====================================
// src/components/graficos/MatrizConfusion.tsx
// =====================================
// Matriz de confusión como mapa de calor de un solo tono: más oscuro = más cajas.
// Es una tabla HTML, así que también es su propia vista en tabla.
import { useState } from "react";
import { Tab, Tabs } from "@heroui/react";
import { numero } from "../../utils/formato";

interface Props {
  /** Las clases y al final "fondo" */
  etiquetas: string[];
  /** filas[real][predicho] */
  filas: number[][];
}

type Modo = "cantidades" | "porcentajes";

export default function MatrizConfusion({ etiquetas, filas }: Props) {
  const [modo, setModo] = useState<Modo>("porcentajes");
  const [celda, setCelda] = useState<{ real: number; predicho: number } | null>(null);
  const fondo = etiquetas.length - 1;

  // En porcentajes, cada fila se lee como "de las cajas reales de esta clase, qué se predijo".
  // La fila fondo (falsas alarmas) no tiene un total real contra el cual dividir:
  // muestra siempre cantidades.
  const totalesFila = filas.map((fila) => fila.reduce((a, b) => a + b, 0));
  const maximo = Math.max(1, ...filas.flatMap((fila, r) => fila.filter((_, p) => !(r === fondo && p === fondo))));
  const enPorcentaje = (r: number) => modo === "porcentajes" && r !== fondo;
  const intensidad = (r: number, p: number) =>
    enPorcentaje(r) ? (totalesFila[r] ? filas[r][p] / totalesFila[r] : 0) : filas[r][p] / maximo;
  const texto = (r: number, p: number) =>
    enPorcentaje(r) ? (totalesFila[r] ? `${numero((filas[r][p] / totalesFila[r]) * 100)} %` : "—") : numero(filas[r][p]);

  const describir = (r: number, p: number) => {
    const cantidad = filas[r][p];
    if (r === fondo) {
      return `Falsas alarmas de ${etiquetas[p]}: ${numero(cantidad)} ${cantidad === 1 ? "vez" : "veces"} el modelo vio ${etiquetas[p]} donde no había nada etiquetado.`;
    }
    const parte = totalesFila[r] ? ` (${numero((cantidad / totalesFila[r]) * 100)} % de las ${numero(totalesFila[r])} cajas de ${etiquetas[r]})` : "";
    if (p === fondo) return `Cajas de ${etiquetas[r]} que el modelo no vio: ${numero(cantidad)}${parte}.`;
    if (r === p) return `Cajas de ${etiquetas[r]} bien detectadas: ${numero(cantidad)}${parte}.`;
    return `Cajas de ${etiquetas[r]} confundidas con ${etiquetas[p]}: ${numero(cantidad)}${parte}.`;
  };

  return (
    <div className="space-y-3">
      <Tabs size="sm" aria-label="Cómo mostrar la matriz" selectedKey={modo} onSelectionChange={(k) => setModo(k as Modo)}>
        <Tab key="porcentajes" title="% de cada clase real" />
        <Tab key="cantidades" title="Cantidades" />
      </Tabs>

      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5 text-xs tabular-nums">
          <thead>
            <tr>
              <th className="px-2 text-left font-normal text-slate-500 dark:text-slate-400">Real ↓ · Predicho →</th>
              {etiquetas.map((e, p) => (
                <th key={e} scope="col" className={`px-2 pb-1 font-medium ${p === fondo ? "italic text-slate-500 dark:text-slate-400" : ""}`}>
                  {e}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((fila, r) => (
              <tr key={etiquetas[r]}>
                <th scope="row" className={`pr-3 text-right font-medium ${r === fondo ? "italic text-slate-500 dark:text-slate-400" : ""}`}>
                  {etiquetas[r]}
                </th>
                {fila.map((_, p) => {
                  // Fondo real predicho como fondo no se cuenta: no tiene sentido
                  if (r === fondo && p === fondo) {
                    return <td key={p} className="h-11 min-w-14 rounded-md text-center text-slate-400">—</td>;
                  }
                  const peso = intensidad(r, p);
                  const activa = celda?.real === r && celda?.predicho === p;
                  return (
                    <td
                      key={p}
                      tabIndex={0}
                      aria-label={describir(r, p)}
                      onPointerEnter={() => setCelda({ real: r, predicho: p })}
                      onPointerLeave={() => setCelda(null)}
                      onFocus={() => setCelda({ real: r, predicho: p })}
                      onBlur={() => setCelda(null)}
                      className={`h-11 min-w-14 cursor-default rounded-md px-2 text-center outline-none transition-[filter] ${
                        activa ? "brightness-110 ring-2 ring-slate-400 dark:ring-slate-300" : ""
                      } ${peso > 0.55 ? "font-semibold text-white" : "text-slate-700 dark:text-slate-200"}`}
                      style={{ background: `color-mix(in srgb, var(--serie-1) ${Math.round(peso * 100)}%, var(--grafico-grilla))` }}
                    >
                      {texto(r, p)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="min-h-5 text-sm text-slate-600 dark:text-slate-300" role="status">
        {celda ? describir(celda.real, celda.predicho) : "Pasá el puntero o el foco por una celda para leerla."}
      </p>
    </div>
  );
}
