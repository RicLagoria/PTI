import csv
import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Pesos de partida oficiales de Ultralytics que se aceptan en un entrenamiento.
# Cualquier otra cosa tiene que ser una versión del registro: pesos_base llega
# en el request y YOLO() abre los .pt con pickle (y descarga URLs), así que un
# valor libre permitiría ejecutar código en el worker.
PESOS_BASE_OFICIALES = ("yolov8n.pt",)

# Las versiones se usan como nombre de carpeta y llegan en las URLs
NOMBRE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CARPETA_ACTIVO = "activo"

# Gráficos que genera Ultralytics y que la API puede servir tal cual. Para las
# versiones sin evaluacion.json (la semilla) son lo único que hay de su validación.
IMAGENES_DE_CORRIDA = (
    "confusion_matrix.png",
    "confusion_matrix_normalized.png",
    "results.png",
    "BoxPR_curve.png",
    "BoxF1_curve.png",
    "BoxP_curve.png",
    "BoxR_curve.png",
)

# Archivos de una corrida de Ultralytics que se guardan con cada versión
ARCHIVOS_DE_CORRIDA = ("results.csv", "args.yaml", "evaluacion.json", *IMAGENES_DE_CORRIDA)


def _obtener_dir_modelos() -> Path:
    env_dir = os.environ.get("MODELOS_DIR")
    if env_dir:
        return Path(env_dir)

    candidatos = [
        Path("datos/modelos"),
        Path("../datos/modelos"),
        Path("../../datos/modelos"),
        Path("../../../datos/modelos"),
        Path("/data/modelos"),
        Path("data/modelos"),
    ]
    for c in candidatos:
        if c.is_dir():
            return c

    ruta = Path("datos/modelos")
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


MODELOS_DIR = _obtener_dir_modelos()

# FastAPI corre los endpoints sync en un pool de hilos: dos activaciones a la vez
# podrían dejar best.pt de una versión y version.txt de la otra
_activando = threading.Lock()


def es_version_valida(version: str) -> bool:
    return bool(NOMBRE_VERSION.match(version or "")) and version != CARPETA_ACTIVO


def carpeta_version(version: str) -> Optional[Path]:
    """Carpeta de una versión publicada, o None si el nombre no es válido o no existe."""
    if not es_version_valida(version):
        return None
    carpeta = MODELOS_DIR / version
    return carpeta if (carpeta / "best.pt").is_file() else None


def version_activa() -> Optional[str]:
    archivo = MODELOS_DIR / CARPETA_ACTIVO / "version.txt"
    if archivo.is_file():
        return archivo.read_text(encoding="utf-8").strip() or None
    return None


def listar_modelos() -> List[Dict]:
    """Lista las versiones registradas de modelos."""
    if not MODELOS_DIR.is_dir():
        return []

    activa = version_activa()
    modelos = []
    for d in sorted(MODELOS_DIR.iterdir()):
        # Las carpetas que empiezan con "." son publicaciones a medio copiar
        if d.is_dir() and d.name != CARPETA_ACTIVO and not d.name.startswith("."):
            meta_file = d / "meta.json"
            best_pt = d / "best.pt"
            if best_pt.is_file():
                meta = {}
                if meta_file.is_file():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                modelos.append({
                    "version": d.name,
                    "activo": d.name == activa,
                    "tamano_mb": round(best_pt.stat().st_size / (1024 * 1024), 2),
                    "meta": meta
                })

    return modelos


def ruta_pesos_activos() -> Optional[Path]:
    # Sin versión activa no se sirve ninguna: elegir una al azar podría poner en
    # producción una corrida que nadie revisó. La activación es siempre explícita.
    activo_pt = MODELOS_DIR / CARPETA_ACTIVO / "best.pt"
    return activo_pt if activo_pt.is_file() else None


def resolver_pesos_base(nombre: str) -> Optional[str]:
    """Ruta (o nombre oficial) de los pesos de partida, o None si no está permitido."""
    if nombre in PESOS_BASE_OFICIALES:
        return nombre
    carpeta = carpeta_version(nombre)
    return str(carpeta / "best.pt") if carpeta else None


def activar_modelo(version: str) -> bool:
    """Activa una versión copiando sus pesos a datos/modelos/activo/best.pt de forma atómica."""
    carpeta = carpeta_version(version)
    if carpeta is None:
        return False

    carpeta_activo = MODELOS_DIR / CARPETA_ACTIVO
    carpeta_activo.mkdir(parents=True, exist_ok=True)

    with _activando:
        # os.replace es atómico: ia-inferencia nunca ve el archivo a medio copiar ni ausente
        temporal = carpeta_activo / f".best.pt.{uuid.uuid4().hex}.tmp"
        try:
            shutil.copy2(carpeta / "best.pt", temporal)
            os.replace(temporal, carpeta_activo / "best.pt")
        finally:
            temporal.unlink(missing_ok=True)

        temporal_version = carpeta_activo / f".version.txt.{uuid.uuid4().hex}.tmp"
        temporal_version.write_text(version, encoding="utf-8")
        os.replace(temporal_version, carpeta_activo / "version.txt")
    return True


def leer_metricas(results_csv: Path) -> Dict:
    """
    Métricas de la época que Ultralytics guardó como best.pt: la de mayor
    fitness, que para detección es 0.1 * mAP50 + 0.9 * mAP50-95.
    """
    try:
        with open(results_csv, "r", encoding="utf-8") as f:
            # Algunas versiones de Ultralytics rellenan los encabezados con espacios
            filas = [{k.strip(): v.strip() for k, v in fila.items()} for fila in csv.DictReader(f)]
        if not filas:
            return {}

        def valor(fila: Dict, columna: str) -> float:
            return float(fila.get(columna) or 0)

        mejor = max(filas, key=lambda f: 0.1 * valor(f, "metrics/mAP50(B)") + 0.9 * valor(f, "metrics/mAP50-95(B)"))
        return {
            "epoca_mejor": int(valor(mejor, "epoch")),
            "epocas_entrenadas": len(filas),
            "precision": round(valor(mejor, "metrics/precision(B)"), 4),
            "recall": round(valor(mejor, "metrics/recall(B)"), 4),
            "map50": round(valor(mejor, "metrics/mAP50(B)"), 4),
            "map50_95": round(valor(mejor, "metrics/mAP50-95(B)"), 4),
        }
    except (OSError, ValueError, KeyError):
        return {}


def leer_historial(results_csv: Path) -> List[Dict]:
    """Pérdidas y métricas de cada época, para dibujar las curvas de entrenamiento."""
    try:
        with open(results_csv, "r", encoding="utf-8") as f:
            filas = [{k.strip(): v.strip() for k, v in fila.items()} for fila in csv.DictReader(f)]
    except OSError:
        return []

    def valor(fila: Dict, columna: str) -> Optional[float]:
        try:
            return round(float(fila[columna]), 4)
        except (KeyError, ValueError):
            return None

    def suma(fila: Dict, prefijo: str) -> Optional[float]:
        partes = [valor(fila, f"{prefijo}/{c}_loss") for c in ("box", "cls", "dfl")]
        return None if None in partes else round(sum(partes), 4)

    return [{
        "epoca": int(valor(fila, "epoch") or 0),
        # Suma de las tres pérdidas de YOLO (cajas, clases y distribución de bordes)
        "perdida_train": suma(fila, "train"),
        "perdida_val": suma(fila, "val"),
        "precision": valor(fila, "metrics/precision(B)"),
        "recall": valor(fila, "metrics/recall(B)"),
        "map50": valor(fila, "metrics/mAP50(B)"),
        "map50_95": valor(fila, "metrics/mAP50-95(B)"),
    } for fila in filas]


def leer_detalle(version: str) -> Optional[Dict]:
    """Evaluación numérica, historial por época y gráficos disponibles de una versión."""
    carpeta = carpeta_version(version)
    if carpeta is None:
        return None
    evaluacion = None
    if (carpeta / "evaluacion.json").is_file():
        with open(carpeta / "evaluacion.json", "r", encoding="utf-8") as f:
            evaluacion = json.load(f)
    return {
        "version": version,
        "evaluacion": evaluacion,
        "historial": leer_historial(carpeta / "results.csv"),
        "imagenes": [n for n in IMAGENES_DE_CORRIDA if (carpeta / n).is_file()],
    }


def ruta_imagen(version: str, nombre: str) -> Optional[Path]:
    """Ruta de un gráfico de la corrida, solo si está en la lista de permitidos."""
    carpeta = carpeta_version(version)
    if carpeta is None or nombre not in IMAGENES_DE_CORRIDA:
        return None
    ruta = carpeta / nombre
    return ruta if ruta.is_file() else None


def publicar_version(version: str, carpeta_corrida: Path, meta: Dict) -> Dict:
    """
    Copia una corrida de Ultralytics al registro como versión nueva: best.pt,
    results.csv, curvas y un meta.json con las métricas. No la activa.
    """
    if not es_version_valida(version):
        raise ValueError(f"Nombre de versión inválido: {version!r}")
    destino = MODELOS_DIR / version
    if destino.exists():
        raise ValueError(f"La versión {version} ya existe en el registro.")
    pesos = carpeta_corrida / "weights" / "best.pt"
    if not pesos.is_file():
        raise ValueError(f"La corrida no generó weights/best.pt (se buscó en {carpeta_corrida}).")

    temporal = MODELOS_DIR / f".publicando-{version}"
    shutil.rmtree(temporal, ignore_errors=True)
    temporal.mkdir(parents=True)
    try:
        shutil.copy2(pesos, temporal / "best.pt")
        for nombre in ARCHIVOS_DE_CORRIDA:
            if (carpeta_corrida / nombre).is_file():
                shutil.copy2(carpeta_corrida / nombre, temporal / nombre)

        meta_completo = {
            "version": version,
            "fecha_creacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **meta,
            "metricas": leer_metricas(temporal / "results.csv"),
        }
        with open(temporal / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta_completo, f, indent=2, ensure_ascii=False)

        temporal.rename(destino)
        return meta_completo
    except BaseException:
        shutil.rmtree(temporal, ignore_errors=True)
        raise


def sembrar_si_vacio(carpeta_semilla: Path, clases_canonicas: List[str]) -> Optional[str]:
    """
    En una instalación nueva el registro está vacío e ia-inferencia no tiene
    modelo. Si es así, publica la corrida semilla (train-3) como primera versión
    y la activa. Devuelve el nombre de la versión sembrada, o None.
    """
    if listar_modelos() or not (carpeta_semilla / "weights" / "best.pt").is_file():
        return None

    # Las clases de la semilla vienen anotadas al lado de los pesos. Sirve si una
    # lista es el principio de la otra; si no, sus índices significan otra cosa.
    # Si tiene clases ya retiradas de la lista canónica, las sigue prediciendo
    # hasta que se active una versión entrenada con la lista nueva.
    archivo_clases = carpeta_semilla / "clases.json"
    clases = json.loads(archivo_clases.read_text(encoding="utf-8")) if archivo_clases.is_file() else None
    comun = min(len(clases or []), len(clases_canonicas))
    if not clases or clases_canonicas[:comun] != clases[:comun]:
        print(f"[REGISTRO] No se siembra {carpeta_semilla.name}: sus clases {clases} "
              f"no son compatibles con las canónicas {clases_canonicas}.")
        return None

    version = carpeta_semilla.name
    publicar_version(version, carpeta_semilla, {"origen": "semilla", "clases": clases})
    if version_activa() is None:
        activar_modelo(version)
    return version
