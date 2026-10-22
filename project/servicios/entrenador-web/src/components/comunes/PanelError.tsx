// Muestra un rechazo de la API con todo lo que hace falta para corregirlo
import { Chip } from "@heroui/react";
import { AlertTriangle } from "lucide-react";
import { ErrorApi } from "../../services/EntrenamientoService";

export default function PanelError({ error }: { error: unknown }) {
  const e = error instanceof ErrorApi ? error : new ErrorApi(error instanceof Error ? error.message : String(error));
  const desconocidas = Object.entries(e.clasesDesconocidas ?? {});

  return (
    <div className="space-y-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
      <p className="flex items-start gap-2 font-medium">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        {e.message}
      </p>

      {desconocidas.length > 0 && (
        <div className="space-y-2">
          <p>Etiquetas que no existen en la lista canónica:</p>
          <div className="flex flex-wrap gap-2">
            {desconocidas.map(([etiqueta, cantidad]) => (
              <Chip key={etiqueta} size="sm" color="danger" variant="flat">
                "{etiqueta}" × {cantidad}
              </Chip>
            ))}
          </div>
        </div>
      )}

      {e.clasesValidas && e.clasesValidas.length > 0 && (
        <p>
          Las válidas son: <span className="font-semibold">{e.clasesValidas.join(", ")}</span>.
        </p>
      )}

      {e.errores && e.errores.length > 0 && (
        <ul className="max-h-48 list-disc space-y-1 overflow-y-auto pl-5 font-mono text-xs">
          {e.errores.map((texto) => (
            <li key={texto}>{texto}</li>
          ))}
          {!!e.erroresOmitidos && <li>… y {e.erroresOmitidos} más.</li>}
        </ul>
      )}
    </div>
  );
}
