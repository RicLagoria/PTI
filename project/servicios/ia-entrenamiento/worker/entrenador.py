import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path

# Permitir importar desde nucleo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nucleo"))

from ultralytics import YOLO
import ensamblado
import registro
import trabajos
from evaluacion import evaluar_modelo

# Métricas de validación que Ultralytics deja en trainer.metrics al cerrar cada época
METRICAS_POR_EPOCA = {
    "metrics/precision(B)": "precision",
    "metrics/recall(B)": "recall",
    "metrics/mAP50(B)": "map50",
    "metrics/mAP50-95(B)": "map50_95",
}


class EntrenamientoCancelado(Exception):
    """Se pidió cancelar el trabajo. No hereda de RuntimeError: el bucle de Ultralytics atrapa esa."""


class Progreso:
    """
    Publica en el trabajo en qué fase está, cuánto avanzó y cuánto le falta, y
    revisa si se pidió cancelarlo. Dentro de cada época avanza por lote, así la
    barra no queda quieta durante épocas largas. El JSON se escribe como mucho
    cada INTERVALO_S segundos; cada escritura es también el latido del worker, y
    solo se hace si el trabajo sigue siendo de este worker (si no, TrabajoPerdido).
    """

    INTERVALO_S = 2.0
    # Antes de esto el ritmo todavía incluye el arranque y la estimación salta mucho
    MINIMO_PARA_ESTIMAR_S = 10.0

    def __init__(self, trabajo_id: str, epocas: int, worker: str, intento: int):
        self.trabajo_id = trabajo_id
        self.epocas = epocas
        self.worker = worker
        self.intento = intento
        self.inicio_entrenamiento = None
        self.ultima_escritura = 0.0
        self.lote = 0
        self.lotes_por_epoca = 1

    def verificar_cancelacion(self):
        if trabajos.cancelacion_pedida(self.trabajo_id):
            raise EntrenamientoCancelado()

    def verificar_que_es_mio(self):
        trabajos.verificar_que_es_mio(self.trabajo_id, self.worker, self.intento)

    def latido(self, *_):
        """
        Para las fases sin progreso medible (copiar el dataset, validar cada época,
        evaluar): renueva el latido sin tocar la barra, así no se lo da por muerto.
        """
        self.verificar_cancelacion()
        ahora = time.time()
        if ahora - self.ultima_escritura < self.INTERVALO_S:
            return
        self.ultima_escritura = ahora
        trabajos.actualizar_si_es_mio(self.trabajo_id, self.worker, self.intento, latido=trabajos.ahora_iso())

    def fase(self, nombre: str, **extra):
        """Cambio de fase: se escribe siempre, sin esperar el intervalo."""
        self.verificar_cancelacion()
        self._escribir({"fase": nombre}, forzar=True, **extra)

    def empezar_entrenamiento(self):
        self.inicio_entrenamiento = time.time()
        self.fase("entrenando", fraccion=0.0)

    def avance(self, epoca: int, fin_de_epoca: bool = False, **extra):
        """epoca empieza en 0. Al cerrar una época, la fracción es exacta: (epoca + 1) / epocas."""
        hechas = epoca + 1 if fin_de_epoca else epoca + min(1.0, self.lote / max(1, self.lotes_por_epoca))
        fraccion = min(1.0, hechas / self.epocas)
        transcurrido = time.time() - (self.inicio_entrenamiento or time.time())
        datos = {"fase": "entrenando", "fraccion": round(fraccion, 4), "transcurrido_s": round(transcurrido)}
        # El ritmo promedio hasta acá ya incluye la validación de cada época
        if fraccion > 0 and transcurrido >= self.MINIMO_PARA_ESTIMAR_S:
            datos["segundos_restantes"] = round(transcurrido * (1 - fraccion) / fraccion)
        self._escribir(datos, forzar=fin_de_epoca, **extra)

    def _escribir(self, datos: dict, forzar: bool = False, fraccion=None, **extra):
        ahora = time.time()
        if not forzar and ahora - self.ultima_escritura < self.INTERVALO_S:
            return
        self.ultima_escritura = ahora
        if fraccion is not None:
            datos["fraccion"] = fraccion
        marca = trabajos.ahora_iso()
        trabajos.actualizar_si_es_mio(
            self.trabajo_id, self.worker, self.intento, progreso={**datos, "actualizado": marca}, latido=marca, **extra
        )


def ejecutar_un_trabajo(trabajo: dict):
    trabajo_id = trabajo["id"]
    # El trabajo ya llega en "ejecutando" y con este worker como dueño: lo marcó
    # reclamar_siguiente_pendiente(). Si es un reintento, empieza de cero.
    worker = trabajo["worker"]
    intento = trabajo.get("intentos", 1)
    print(f"[WORKER] Iniciando entrenamiento para trabajo {trabajo_id} (intento {intento})...")

    epocas = trabajo.get("epocas", 50)
    imgsz = trabajo.get("imgsz", 640)
    pesos_base = trabajo.get("pesos_base", "yolov8n.pt")
    fraccion_validacion = trabajo.get("fraccion_validacion", ensamblado.FRACCION_VALIDACION)

    # Cada intento trabaja en TRABAJOS_DIR/<id>/intento-N/: el dataset armado y la corrida
    # de Ultralytics (que si no se escribiría en ./runs, dentro del contenedor). Separados
    # para que un worker dado por muerto que siga vivo no comparta archivos con el nuevo.
    carpeta_trabajo = trabajos.carpeta_intento(trabajo_id, intento)
    carpeta_dataset = carpeta_trabajo / "dataset"
    exito = False
    progreso = Progreso(trabajo_id, epocas, worker, intento)

    try:
        progreso.fase("preparando")
        # Las copias del dataset de intentos anteriores (su worker murió sin limpiar)
        for anterior in range(1, intento):
            shutil.rmtree(trabajos.carpeta_intento(trabajo_id, anterior) / "dataset", ignore_errors=True)

        # La API ya lo validó, pero el registro pudo cambiar mientras el trabajo esperaba en la cola
        pesos = registro.resolver_pesos_base(pesos_base)
        if pesos is None:
            raise ValueError(f"Pesos de partida no permitidos o inexistentes: {pesos_base}")

        ruta_yaml, resumen = ensamblado.armar_dataset(
            trabajo["datasets"], carpeta_dataset, semilla=trabajo_id,
            fraccion_validacion=fraccion_validacion, al_copiar=progreso.latido,
        )
        print(f"[WORKER] Dataset armado: {resumen['imagenes_train']} imágenes de entrenamiento, "
              f"{resumen['imagenes_val']} de validación.")

        model = YOLO(pesos)

        def on_train_epoch_start(trainer):
            progreso.lote = 0
            progreso.lotes_por_epoca = len(trainer.train_loader)

        def on_train_batch_end(trainer):
            progreso.verificar_cancelacion()
            progreso.lote += 1
            progreso.avance(trainer.epoch)

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
            progreso.avance(trainer.epoch, fin_de_epoca=True, progreso_epocas=epoca_actual, metricas=metricas)
            print(f"[WORKER] Época {epoca_actual}/{epocas} completada.")

        model.add_callback("on_pretrain_routine_start", lambda trainer: progreso.verificar_cancelacion())
        model.add_callback("on_train_start", lambda trainer: progreso.empezar_entrenamiento())
        model.add_callback("on_train_epoch_start", on_train_epoch_start)
        model.add_callback("on_train_batch_end", on_train_batch_end)
        model.add_callback("on_fit_epoch_end", on_fit_epoch_end)
        # La validación de cada época no tiene barra propia, pero tiene que seguir dando latido
        model.add_callback("on_val_batch_end", progreso.latido)

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

        carpeta_corrida = Path(model.trainer.save_dir)

        # Evaluación numérica de best.pt (matriz de confusión, métricas por clase,
        # umbral recomendado). Si falla, el modelo entrenado igual se publica.
        error_evaluacion = None
        progreso.fase("evaluando", fraccion=1.0)
        try:
            evaluacion = evaluar_modelo(
                str(carpeta_corrida / "weights" / "best.pt"), ruta_yaml, imgsz, carpeta_trabajo, resumen["clases"],
                al_avanzar=progreso.latido,
            )
            with open(carpeta_corrida / "evaluacion.json", "w", encoding="utf-8") as f:
                json.dump(evaluacion, f, indent=2, ensure_ascii=False)
        except (EntrenamientoCancelado, trabajos.TrabajoPerdido):
            raise
        except Exception as e:
            error_evaluacion = str(e)
            print(f"[WORKER] No se pudo evaluar el trabajo {trabajo_id}: {e}")

        # Última oportunidad de cancelar: después de esto la versión queda publicada
        progreso.verificar_cancelacion()
        progreso.verificar_que_es_mio()
        version_nueva = f"v_{trabajo_id}"
        meta = registro.publicar_version(version_nueva, carpeta_corrida, {
            "origen": "entrenamiento",
            "trabajo_id": trabajo_id,
            "datasets": trabajo["datasets"],
            "epocas": epocas,
            "imgsz": imgsz,
            "pesos_base": pesos_base,
            "clases": resumen["clases"],
            "imagenes_train": resumen["imagenes_train"],
            "imagenes_val": resumen["imagenes_val"],
            "fraccion_validacion": fraccion_validacion,
            "error_evaluacion": error_evaluacion,
        })

        # Se publica pero no se activa: activar es un paso explícito (POST /modelos/{v}/activar)
        trabajos.finalizar_si_es_mio(
            trabajo_id, worker, intento, "completado",
            progreso_epocas=meta["metricas"].get("epocas_entrenadas", epocas),
            version_generada=version_nueva,
            metricas=meta["metricas"],
        )
        exito = True
        print(f"[WORKER] Trabajo {trabajo_id} completado con éxito. Versión: {version_nueva}")

    except trabajos.TrabajoPerdido:
        # Lo dieron por muerto y otro worker lo retomó (o ya terminó): no se escribe nada
        print(f"[WORKER] El trabajo {trabajo_id} ya no es de este worker (intento {intento}); se abandona.")

    except EntrenamientoCancelado:
        actual = trabajos.obtener_trabajo(trabajo_id) or {}
        epoca = actual.get("progreso_epocas", 0)
        print(f"[WORKER] Trabajo {trabajo_id} cancelado a pedido.")
        try:
            trabajos.finalizar_si_es_mio(
                trabajo_id, worker, intento, "cancelado",
                error=f"Cancelado a pedido después de {epoca} de {epocas} épocas. No se publicó ninguna versión.",
            )
        except trabajos.TrabajoPerdido:
            pass
        # Un trabajo cancelado no deja nada que diagnosticar
        exito = True

    except Exception as e:
        print(f"[WORKER ERROR] Falló entrenamiento de {trabajo_id}: {e}")
        try:
            trabajos.finalizar_si_es_mio(trabajo_id, worker, intento, "fallido", error=str(e))
        except trabajos.TrabajoPerdido:
            pass

    finally:
        # La copia del dataset no hace falta nunca más. La corrida se borra si ya
        # quedó publicada en el registro o se canceló; si falló, se deja para diagnosticar.
        shutil.rmtree(carpeta_dataset, ignore_errors=True)
        if exito:
            # Con todos sus intentos, incluidos los de workers que murieron antes
            shutil.rmtree(carpeta_trabajo.parent, ignore_errors=True)
        else:
            # Si falló antes de que Ultralytics escribiera algo, no queda nada que diagnosticar
            for carpeta in (carpeta_trabajo, carpeta_trabajo.parent):
                try:
                    carpeta.rmdir()
                except OSError:
                    pass


def bucle_worker():
    # Identifica a esta réplica cuando se levantan varias (docker compose --scale)
    nombre_worker = f"{socket.gethostname()}-{os.getpid()}"
    print(f"[WORKER] Worker {nombre_worker} iniciado. Esperando trabajos...")
    while True:
        trabajo = trabajos.reclamar_siguiente_pendiente(nombre_worker)
        if trabajo:
            ejecutar_un_trabajo(trabajo)
        else:
            time.sleep(5)


if __name__ == "__main__":
    bucle_worker()
