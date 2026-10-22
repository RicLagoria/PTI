import { claseRecuadro } from "./estilos";

export default function Metrica({ etiqueta, valor, detalle }: { etiqueta: string; valor: string; detalle?: string }) {
  return (
    <div className={claseRecuadro}>
      <p className="text-xs text-slate-500 dark:text-slate-400">{etiqueta}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{valor}</p>
      {detalle && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{detalle}</p>}
    </div>
  );
}
