"""
Demostración del caso de concurrencia de la Entrega 3: varios workers de
entrenamiento tomando trabajos de la misma cola al mismo tiempo.

Usa el código real de la cola (project/servicios/ia-entrenamiento/nucleo/trabajos.py)
sobre una carpeta temporal. No entrena ningún modelo: cada worker "trabaja" unos
milisegundos y marca el trabajo como completado.

Modos:
  sin-arreglo  toma los trabajos como lo hacía el worker originalmente:
               leer el pendiente más viejo y después marcarlo "ejecutando" (dos pasos).
  con-arreglo  usa trabajos.reclamar_siguiente_pendiente(), que reclama cada
               trabajo de forma atómica.

Uso:
  python docs/pdc/entrega-3-comunicacion/demo_concurrencia_cola.py --modo sin-arreglo
  python docs/pdc/entrega-3-comunicacion/demo_concurrencia_cola.py --modo con-arreglo
Opciones: --trabajos 20 --workers 5 --trabajo-ms 50
"""
import argparse
import multiprocessing as mp
import os
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
NUCLEO = RAIZ / "project" / "servicios" / "ia-entrenamiento" / "nucleo"


def worker(nombre, modo, barrera, resultados, trabajo_ms):
    sys.path.insert(0, str(NUCLEO))
    import trabajos

    barrera.wait()  # todos los workers arrancan a la vez
    while True:
        try:
            if modo == "sin-arreglo":
                trabajo = trabajos.obtener_siguiente_pendiente()
                if trabajo is None:
                    break
                trabajos.actualizar_trabajo(trabajo["id"], estado="ejecutando")
            else:
                trabajo = trabajos.reclamar_siguiente_pendiente(nombre)
                if trabajo is None:
                    break
        except Exception as e:
            # Un JSON leído a medio escribir rompe la lectura: también es parte del problema
            resultados.put(("error", nombre, f"{type(e).__name__}: {e}"))
            continue

        resultados.put(("tomado", nombre, trabajo["id"]))
        time.sleep(trabajo_ms / 1000)  # simula el entrenamiento
        trabajos.actualizar_trabajo(trabajo["id"], estado="completado")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modo", choices=["sin-arreglo", "con-arreglo"], required=True)
    parser.add_argument("--trabajos", type=int, default=20)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--trabajo-ms", type=int, default=50)
    args = parser.parse_args()

    carpeta = tempfile.mkdtemp(prefix="cola-demo-")
    # La cola lee TRABAJOS_DIR al importarse; los procesos hijos heredan la variable
    os.environ["TRABAJOS_DIR"] = carpeta
    sys.path.insert(0, str(NUCLEO))
    import trabajos

    ids = [trabajos.encolar_trabajo(datasets=["demo"], epocas=1)["id"] for _ in range(args.trabajos)]
    print(f"Modo: {args.modo} | {args.trabajos} trabajos encolados | {args.workers} workers en paralelo")
    print(f"Cola en: {carpeta}\n")

    barrera = mp.Barrier(args.workers)
    resultados = mp.Queue()
    procesos = [
        mp.Process(target=worker, args=(f"worker-{i + 1}", args.modo, barrera, resultados, args.trabajo_ms))
        for i in range(args.workers)
    ]
    for p in procesos:
        p.start()
    for p in procesos:
        p.join()

    tomados_por = defaultdict(list)
    errores = []
    while not resultados.empty():
        tipo, nombre, dato = resultados.get()
        if tipo == "tomado":
            tomados_por[dato].append(nombre)
        else:
            errores.append((nombre, dato))

    duplicados = {t: ws for t, ws in tomados_por.items() if len(ws) > 1}
    sin_tomar = [t for t in ids if t not in tomados_por]
    ejecuciones = sum(len(ws) for ws in tomados_por.values())

    for t, ws in sorted(duplicados.items()):
        print(f"  DUPLICADO  trabajo {t} ejecutado {len(ws)} veces por: {', '.join(sorted(ws))}")
    for nombre, error in errores[:5]:
        print(f"  ERROR      {nombre}: {error}")

    print()
    print(f"Ejecuciones totales:        {ejecuciones} (esperadas: {args.trabajos})")
    print(f"Trabajos ejecutados 2+ veces: {len(duplicados)}")
    print(f"Trabajos sin ejecutar:       {len(sin_tomar)}")
    print(f"Errores de lectura:          {len(errores)}")
    ok = not duplicados and not sin_tomar and not errores
    print("\nRESULTADO:", "OK, cada trabajo se ejecutó exactamente una vez" if ok
          else "FALLA, hay trabajos repetidos, perdidos o lecturas corruptas")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
