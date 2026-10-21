"""
Arma, para un trabajo de entrenamiento, el dataset en el formato que espera
Ultralytics a partir de los aportes elegidos.

Ultralytics encuentra la etiqueta de cada imagen reemplazando "images" por
"labels" en su ruta, por eso estas carpetas van en inglés.
"""
import random
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

import datasets
from clases import obtener_clases_canonicas

FRACCION_VALIDACION = 0.25


def cantidad_validacion(total: int, fraccion: float) -> int:
    """
    Cuántas imágenes de un aporte van a validación. Redondea .5 hacia arriba (y no
    al par, como round()) para que entrenador-web pueda anticipar la misma cuenta.
    Con una sola imagen no hay qué separar: va entera a entrenamiento.
    """
    if total < 2:
        return 0
    return min(total - 1, max(1, int(total * fraccion + 0.5)))


class ErrorEnsamblado(Exception):
    pass


def armar_dataset(
    ids_datasets: List[str], destino: Path, semilla: str, fraccion_validacion: float = FRACCION_VALIDACION
) -> Tuple[Path, Dict]:
    """
    Copia los aportes a destino/{images,labels}/{train,val}/ y escribe
    destino/dataset.yaml. Devuelve (ruta del yaml, resumen).

    El split se hace dentro de cada aporte, para que todos tengan imágenes en
    validación, y es reproducible: depende solo de `semilla` (el id del trabajo).
    """
    clases = obtener_clases_canonicas()
    shutil.rmtree(destino, ignore_errors=True)
    for parte in ("train", "val"):
        (destino / "images" / parte).mkdir(parents=True)
        (destino / "labels" / parte).mkdir(parents=True)

    azar = random.Random(semilla)
    resumen = {
        "clases": clases,
        "fraccion_validacion": fraccion_validacion,
        "imagenes_train": 0,
        "imagenes_val": 0,
        "por_dataset": {},
    }

    for dataset_id in dict.fromkeys(ids_datasets):
        carpeta = datasets.carpeta_de(dataset_id)
        if carpeta is None:
            raise ErrorEnsamblado(f"El dataset {dataset_id} no existe (¿se borró después de encolar el trabajo?).")
        meta = datasets.leer_meta(dataset_id)

        # Los índices de sus etiquetas apuntan a la lista vigente cuando se subió. Sirve si
        # una lista es el principio de la otra: o se agregaron clases al final (el aporte
        # simplemente no las tiene) o se retiraron del final (sus cajas se descartan abajo).
        clases_dataset = meta.get("clases") or []
        comun = min(len(clases), len(clases_dataset))
        if clases[:comun] != clases_dataset[:comun]:
            raise ErrorEnsamblado(
                f"El dataset {dataset_id} se convirtió con las clases {clases_dataset}, incompatibles con la "
                f"lista canónica {clases}: alguien reordenó o borró clases del medio en "
                f"contratos/clases.json. Hay que volver a subir ese aporte."
            )

        descartadas = 0
        imagenes = sorted(p for p in (carpeta / "imagenes").iterdir() if p.is_file())
        azar.shuffle(imagenes)
        cantidad_val = cantidad_validacion(len(imagenes), fraccion_validacion)

        for i, imagen in enumerate(imagenes):
            parte = "val" if i < cantidad_val else "train"
            # El prefijo evita choques de nombres entre aportes distintos
            nombre = f"{dataset_id}_{imagen.stem}"
            shutil.copy2(imagen, destino / "images" / parte / f"{nombre}{imagen.suffix}")
            lineas = (carpeta / "etiquetas" / f"{imagen.stem}.txt").read_text(encoding="utf-8").splitlines()
            # Cajas de clases retiradas de la lista canónica: quedan como fondo
            vigentes = [l for l in lineas if l.strip() and int(l.split()[0]) < len(clases)]
            descartadas += len([l for l in lineas if l.strip()]) - len(vigentes)
            (destino / "labels" / parte / f"{nombre}.txt").write_text(
                "\n".join(vigentes) + "\n" if vigentes else "", encoding="utf-8"
            )

        resumen["imagenes_train"] += len(imagenes) - cantidad_val
        resumen["imagenes_val"] += cantidad_val
        resumen["por_dataset"][dataset_id] = {"train": len(imagenes) - cantidad_val, "val": cantidad_val}
        if descartadas:
            resumen["por_dataset"][dataset_id]["cajas_de_clases_retiradas"] = descartadas

    if resumen["imagenes_train"] == 0 or resumen["imagenes_val"] == 0:
        raise ErrorEnsamblado(
            "Hacen falta al menos 2 imágenes en total para tener entrenamiento y validación "
            f"(hay {resumen['imagenes_train']} de entrenamiento y {resumen['imagenes_val']} de validación)."
        )

    ruta_yaml = destino / "dataset.yaml"
    with open(ruta_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "path": str(destino.resolve()),
            "train": "images/train",
            "val": "images/val",
            "names": {i: c for i, c in enumerate(clases)},
        }, f, allow_unicode=True, sort_keys=False)

    return ruta_yaml, resumen
