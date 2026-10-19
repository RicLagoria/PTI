import shutil
import sys
import time
from pathlib import Path

# Permitir importar desde nucleo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nucleo"))

from ultralytics import YOLO
import ensamblado
import registro
import trabajos

# Métricas de validación que Ultralytics deja en trainer.metrics al cerrar cada época
METRICAS_POR_EPOCA = {
    "metrics/precision(B)": "precision",
    "metrics/recall(B)": "recall",
    "metrics/mAP50(B)": "map50",
    "metrics/mAP50-95(B)": "map50_95",
}


def ejecutar_un_trabajo(trabajo: dict):
    trabajo_id = trabajo["id"]
    print(f"[WORKER] Iniciando entrenamiento para trabajo {trabajo_id}...")
    trabajos.actualizar_trabajo(trabajo_id, estado="ejecutando")

    epocas = trabajo.get("epocas", 50)
    imgsz = trabajo.get("imgsz", 640)
    pesos_base = trabajo.get("pesos_base", "yolov8n.pt")

    # Todo lo de este trabajo vive en TRABAJOS_DIR/<id>/: el dataset armado y la
    # corrida de Ultralytics (que si no se escribiría en ./runs, dentro del contenedor)
    carpeta_trabajo = (trabajos.TRABAJOS_DIR / trabajo_id).resolve()
    carpeta_dataset = carpeta_trabajo / "dataset"
    exito = False

    try:
        # La API ya lo validó, pero el registro pudo cambiar mientras el trabajo esperaba en la cola
        pesos = registro.resolver_pesos_base(pesos_base)
        if pesos is None:
            raise ValueError(f"Pesos de partida no permitidos o inexistentes: {pesos_base}")

        ruta_yaml, resumen = ensamblado.armar_dataset(trabajo["datasets"], carpeta_dataset, semilla=trabajo_id)
        print(f"[WORKER] Dataset armado: {resumen['imagenes_train']} imágenes de entrenamiento, "
              f"{resumen['imagenes_val']} de validación.")

        model = YOLO(pesos)

        def on_fit_epoch_end(trainer):
            epoca_actual = trainer.epoch + 1
            # Ultralytics vuelve a llamar este callback en la evaluación final de
            # best.pt, ya terminadas las épocas; esas métricas las guarda la publicación
            if epoca_actual > epocas:
                return
            metricas = {"epoca": epoca_actual, "total_epocas": epocas}
            # Pérdida media de entrenamiento de la época (box + cls + dfl). Según la
            # versión de Ultralytics, tloss es un tensor o un diccionario por componente.
            perdidas = trainer.tloss
            try:
                if isinstance(perdidas, dict):
                    metricas["perdida"] = round(sum(float(v) for v in perdidas.values()), 4)
                elif perdidas is not None:
                    metricas["perdida"] = round(float(perdidas.sum()), 4)
            except (TypeError, ValueError):
                pass
            for clave, nombre in METRICAS_POR_EPOCA.items():
                if clave in (trainer.metrics or {}):
                    metricas[nombre] = round(float(trainer.metrics[clave]), 4)
            trabajos.actualizar_trabajo(trabajo_id, progreso_epocas=epoca_actual, metricas=metricas)
            print(f"[WORKER] Época {epoca_actual}/{epocas} completada.")

        model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

        model.train(
            data=str(ruta_yaml),
            epochs=epocas,
            imgsz=imgsz,
            batch=2,
            device="cpu",
            workers=2,
            project=str(carpeta_trabajo),
            name="corrida",
            exist_ok=True,
            verbose=False
        )

        version_nueva = f"v_{trabajo_id}"
        meta = registro.publicar_version(version_nueva, Path(model.trainer.save_dir), {
            "origen": "entrenamiento",
            "trabajo_id": trabajo_id,
            "datasets": trabajo["datasets"],
            "epocas": epocas,
            "imgsz": imgsz,
            "pesos_base": pesos_base,
            "clases": resumen["clases"],
            "imagenes_train": resumen["imagenes_train"],
            "imagenes_val": resumen["imagenes_val"],
        })

        # Se publica pero no se activa: activar es un paso explícito (POST /modelos/{v}/activar)
        trabajos.actualizar_trabajo(
            trabajo_id,
            estado="completado",
            progreso_epocas=meta["metricas"].get("epocas_entrenadas", epocas),
            version_generada=version_nueva,
            metricas=meta["metricas"]
        )
        exito = True
        print(f"[WORKER] Trabajo {trabajo_id} completado con éxito. Versión: {version_nueva}")

    except Exception as e:
        print(f"[WORKER ERROR] Falló entrenamiento de {trabajo_id}: {e}")
        trabajos.actualizar_trabajo(trabajo_id, estado="fallido", error=str(e))

    finally:
        # La copia del dataset no hace falta nunca más. La corrida se borra si ya
        # quedó publicada en el registro; si falló, se deja para poder diagnosticar.
        shutil.rmtree(carpeta_dataset, ignore_errors=True)
        if exito:
            shutil.rmtree(carpeta_trabajo, ignore_errors=True)
        else:
            # Si falló antes de que Ultralytics escribiera algo, no queda nada que diagnosticar
            try:
                carpeta_trabajo.rmdir()
            except OSError:
                pass


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
