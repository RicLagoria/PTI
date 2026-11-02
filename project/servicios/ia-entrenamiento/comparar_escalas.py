"""
Compara versiones del modelo sobre los mismos aportes, separando por escala.

El mAP que publica un entrenamiento no sirve para comparar dos versiones que no
se entrenaron con los mismos aportes: cada una se midió contra su propio split
de validación. Y en cuanto se mezclan escalas deja de servir incluso para una
sola versión, porque un número solo no dice si mejoró en grueso o empeoró en
fino. Este script contesta eso: corre la validación de cada versión sobre cada
grupo de aportes y pone los números lado a lado.

**Los aportes que se le pasen tienen que ser los mismos para todas las versiones
y, para que el número signifique algo, no haber entrenado a ninguna.** El script
avisa cuando no es así (lee `datasets` del meta de cada versión), pero no se
niega: comparar sobre datos vistos sigue sirviendo para ordenar dos modelos
entre sí, solo que los valores absolutos salen optimistas.

Los aportes se agrupan por su escala, que está en el meta de los derivados (ver
nucleo/ventanas.py); los que no la tienen son de escala 1.

Uso, desde el repo:

    docker compose -p pti-ia -f despliegue/compose.ia.yml run --rm \\
        ia-entrenamiento-api python comparar_escalas.py \\
        --datasets <id-fino>,<id-4x>

    # y para comparar solo dos versiones:
    ... --datasets <ids> --versiones v_abc123456789,v_def123456789
"""
import argparse
import contextlib
import logging
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "nucleo"))
sys.path.insert(0, str(RAIZ / "worker"))

import datasets as datasets_mod  # noqa: E402
import dispositivos  # noqa: E402
import registro  # noqa: E402
from clases import obtener_clases_canonicas  # noqa: E402
from ensamblado import armar_dataset  # noqa: E402
from evaluacion import evaluar_modelo  # noqa: E402

# Casi todo a validación: lo que se quiere medir es el aporte entero, no una
# muestra. armar_dataset exige al menos una imagen de cada lado, así que queda
# una sola en entrenamiento, que no se usa para nada acá.
FRACCION_CASI_TODO = 0.99


@contextlib.contextmanager
def sin_ruido():
    """
    Se traga lo que escriben Ultralytics y sus barras de progreso.

    Son dos validaciones por versión y por escala, cada una con su barra: el
    producto de este script es la tabla del final, y con el ruido queda
    enterrada. Los errores no se pierden, porque una excepción sigue subiendo.
    """
    # redirect_stdout no alcanza: Ultralytics escribe el resumen por su propio
    # logger, que se quedó con una referencia al stream al importarse.
    log = logging.getLogger("ultralytics")
    nivel = log.level
    log.setLevel(logging.ERROR)
    devnull = open(os.devnull, "w")
    try:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            yield
    finally:
        devnull.close()
        log.setLevel(nivel)


def escala_de(dataset_id: str) -> int:
    """La escala de un aporte: la del meta si es derivado, y 1 si se subió tal cual."""
    meta = datasets_mod.leer_meta(dataset_id) or {}
    return int(meta.get("escala") or 1)


def nombre_de(dataset_id: str) -> str:
    meta = datasets_mod.leer_meta(dataset_id) or {}
    return meta.get("nombre") or dataset_id


def avisar_si_entreno(versiones: List[str], ids: List[str]) -> None:
    """Un aporte que entrenó a una versión le da ventaja al medirla."""
    for version in versiones:
        usados = set((registro.leer_meta_version(version) or {}).get("datasets") or [])
        contaminados = [i for i in ids if i in usados]
        if contaminados:
            print(
                f"  AVISO: {version} se entrenó con "
                f"{', '.join(nombre_de(i) for i in contaminados)}: sus números salen optimistas."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--datasets", required=True, help="ids de aportes, separados por coma")
    parser.add_argument("--versiones", help="versiones a comparar (por defecto, todas las de segmentación)")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--dispositivo", default=None, choices=["cpu", "gpu"])
    args = parser.parse_args()

    ids = [i.strip() for i in args.datasets.split(",") if i.strip()]
    faltan = [i for i in ids if datasets_mod.carpeta_de(i) is None]
    if faltan:
        raise SystemExit(f"Estos aportes no existen: {', '.join(faltan)}")

    if args.versiones:
        versiones = [v.strip() for v in args.versiones.split(",") if v.strip()]
    else:
        # Solo las de segmentación: una de detección no tiene contornos que medir
        versiones = [m["version"] for m in registro.listar_modelos() if m["tarea"] == "segment"]
    if not versiones:
        raise SystemExit("No hay versiones de segmentación en el registro.")

    dispositivo = args.dispositivo or ("gpu" if dispositivos.describir()["gpu_disponible"] else "cpu")
    device, batch = dispositivos.resolver(dispositivo)
    clases = obtener_clases_canonicas()

    por_escala: Dict[int, List[str]] = defaultdict(list)
    for i in ids:
        por_escala[escala_de(i)].append(i)

    print(f"versiones: {', '.join(versiones)}")
    print(f"dispositivo: {dispositivo} (lote {batch})  imgsz: {args.imgsz}")
    for escala, grupo in sorted(por_escala.items(), reverse=True):
        print(f"  escala {escala}: {', '.join(nombre_de(i) for i in grupo)}")
    avisar_si_entreno(versiones, ids)

    resultados: Dict[str, Dict[int, Dict]] = defaultdict(dict)
    with tempfile.TemporaryDirectory(prefix="comparar-") as tmp:
        for escala, grupo in sorted(por_escala.items(), reverse=True):
            carpeta = Path(tmp) / f"escala-{escala}"
            with sin_ruido():
                ruta_yaml, resumen = armar_dataset(
                    grupo, carpeta, semilla="comparar-escalas",
                    fraccion_validacion=FRACCION_CASI_TODO, tarea="segment",
                )
            print(f"\n=== escala {escala}: {resumen['imagenes_val']} imágenes de validación ===")
            for version in versiones:
                pesos = registro.carpeta_version(version)
                if pesos is None:
                    print(f"  {version}: no está en el registro, se saltea")
                    continue
                with sin_ruido():
                    evaluacion = evaluar_modelo(
                        str(pesos / "best.pt"), ruta_yaml, args.imgsz, carpeta, clases,
                        device=device, batch=batch,
                    )
                resultados[version][escala] = evaluacion
                m = evaluacion["metricas"]
                print(f"  {version}: mAP50-95 {m['map50_95']}  recall {m['recall']}")

    print("\n" + "=" * 78)
    print("mAP50-95 de la máscara (el contorno, no la caja que lo encierra)")
    escalas = sorted(por_escala, reverse=True)
    print(f"{'version':<22}" + "".join(f"{'escala ' + str(e):>14}" for e in escalas))
    for version in versiones:
        fila = f"{version:<22}"
        for escala in escalas:
            ev = resultados.get(version, {}).get(escala)
            mascara = (ev or {}).get("metricas_mascara") or {}
            valor = mascara.get("map50_95")
            fila += f"{(f'{valor * 100:.1f} %' if valor is not None else '—'):>14}"
        print(fila)

    print("\nmAP50-95 de la caja")
    print(f"{'version':<22}" + "".join(f"{'escala ' + str(e):>14}" for e in escalas))
    for version in versiones:
        fila = f"{version:<22}"
        for escala in escalas:
            ev = resultados.get(version, {}).get(escala)
            valor = ((ev or {}).get("metricas") or {}).get("map50_95")
            fila += f"{(f'{valor * 100:.1f} %' if valor is not None else '—'):>14}"
        print(fila)

    print(
        "\nLo que hay que mirar es si una versión mejora en la escala gruesa sin "
        "empeorar en la fina.\nUn solo número que mezcle las dos no lo dice."
    )


if __name__ == "__main__":
    main()
