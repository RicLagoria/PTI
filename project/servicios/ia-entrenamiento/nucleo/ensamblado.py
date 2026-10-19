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

FRACCION_VALIDACION = 0.2


class ErrorEnsamblado(Exception):
    pass


def armar_dataset(ids_datasets: List[str], destino: Path, semilla: str) -> Tuple[Path, Dict]:
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
    resumen = {"clases": clases, "imagenes_train": 0, "imagenes_val": 0, "por_dataset": {}}

    for dataset_id in dict.fromkeys(ids_datasets):
        carpeta = datasets.carpeta_de(dataset_id)
        if carpeta is None:
            raise ErrorEnsamblado(f"El dataset {dataset_id} no existe (¿se borró después de encolar el trabajo?).")
        meta = datasets.leer_meta(dataset_id)

        # Los índices de sus etiquetas apuntan a la lista vigente cuando se subió
        clases_dataset = meta.get("clases") or []
        if clases[:len(clases_dataset)] != clases_dataset:
            raise ErrorEnsamblado(
                f"El dataset {dataset_id} se convirtió con las clases {clases_dataset}, que ya no son el "
                f"principio de la lista canónica {clases}. Alguien reordenó o borró clases en "
                f"contratos/clases.json: hay que volver a subir ese aporte."
            )

        imagenes = sorted(p for p in (carpeta / "imagenes").iterdir() if p.is_file())
        azar.shuffle(imagenes)
        # Con una sola imagen no hay qué separar: va entera a entrenamiento
        cantidad_val = max(1, round(len(imagenes) * FRACCION_VALIDACION)) if len(imagenes) >= 2 else 0

        for i, imagen in enumerate(imagenes):
            parte = "val" if i < cantidad_val else "train"
            # El prefijo evita choques de nombres entre aportes distintos
            nombre = f"{dataset_id}_{imagen.stem}"
            shutil.copy2(imagen, destino / "images" / parte / f"{nombre}{imagen.suffix}")
            shutil.copy2(carpeta / "etiquetas" / f"{imagen.stem}.txt", destino / "labels" / parte / f"{nombre}.txt")

        resumen["imagenes_train"] += len(imagenes) - cantidad_val
        resumen["imagenes_val"] += cantidad_val
        resumen["por_dataset"][dataset_id] = {"train": len(imagenes) - cantidad_val, "val": cantidad_val}

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
