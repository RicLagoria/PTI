import os
import sys
import time
from pathlib import Path

# Permitir importar desde nucleo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nucleo"))

from ultralytics import YOLO
import trabajos
import registro
import clases


def ejecutar_un_trabajo(trabajo: dict):
    trabajo_id = trabajo["id"]
    print(f"[WORKER] Iniciando entrenamiento para trabajo {trabajo_id}...")
    trabajos.actualizar_trabajo(trabajo_id, estado="ejecutando")

    epocas = trabajo.get("epocas", 50)
    imgsz = trabajo.get("imgsz", 640)
    pesos_base = trabajo.get("pesos_base", "yolov8n.pt")

    try:
        model = YOLO(pesos_base)

        def on_fit_epoch_end(trainer):
            epoca_actual = trainer.epoch + 1
            perdida = float(getattr(trainer, "loss", 0.0))
            trabajos.actualizar_trabajo(
                trabajo_id,
                progreso_epocas=epoca_actual,
                metricas={"epoca": epoca_actual, "total_epocas": epocas, "perdida": perdida}
            )
            print(f"[WORKER] Época {epoca_actual}/{epocas} completada.")

        model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

        # Buscar dataset.yaml en las carpetas de datos
        candidatos_yaml = [
            Path("Dataset/dataset.yaml"),
            Path("datos/datasets/dataset.yaml"),
            Path("../datos/datasets/dataset.yaml"),
            Path("../../datos/datasets/dataset.yaml"),
        ]
        ruta_yaml = "Dataset/dataset.yaml"
        for c in candidatos_yaml:
            if c.is_file():
                ruta_yaml = str(c)
                break

        results = model.train(
            data=ruta_yaml,
            epochs=epocas,
            imgsz=imgsz,
            batch=2,
            device="cpu",
            workers=2,
            verbose=False
        )

        version_nueva = f"v_{trabajo_id}"
        carpeta_modelo = registro.MODELOS_DIR / version_nueva
        carpeta_modelo.mkdir(parents=True, exist_ok=True)

        # Copiar best.pt si se generó
        save_dir = Path(results.save_dir) if hasattr(results, "save_dir") else None
        if save_dir and (save_dir / "weights" / "best.pt").is_file():
            import shutil
            shutil.copy2(save_dir / "weights" / "best.pt", carpeta_modelo / "best.pt")

        trabajos.actualizar_trabajo(
            trabajo_id,
            estado="completado",
            progreso_epocas=epocas,
            version_generada=version_nueva
        )
        print(f"[WORKER] Trabajo {trabajo_id} completado con éxito. Versión: {version_nueva}")

    except Exception as e:
        print(f"[WORKER ERROR] Falló entrenamiento de {trabajo_id}: {e}")
        trabajos.actualizar_trabajo(trabajo_id, estado="fallido", error=str(e))


def bucle_worker():
    print("[WORKER] Servicio worker de entrenamiento iniciado. Esperando trabajos...")
    while True:
        trabajo = trabajos.obtener_siguiente_pendiente()
        if trabajo:
            ejecutar_un_trabajo(trabajo)
        else:
            time.sleep(5)


if __name__ == "__main__":
    bucle_worker()

