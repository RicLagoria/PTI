import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _obtener_dir_trabajos() -> Path:
    env_dir = os.environ.get("TRABAJOS_DIR")
    if env_dir:
        return Path(env_dir)

    candidatos = [
        Path("datos/trabajos"),
        Path("../datos/trabajos"),
        Path("../../datos/trabajos"),
        Path("/data/trabajos"),
        Path("data/trabajos"),
    ]
    for c in candidatos:
        if c.is_dir():
            return c

    ruta = Path("datos/trabajos")
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


TRABAJOS_DIR = _obtener_dir_trabajos()

# Cada trabajo es un grupo de archivos en TRABAJOS_DIR, todos con el id como nombre:
#   <id>.json       el trabajo (lo reescriben la API y el worker, siempre de forma atómica)
#   <id>.lock       reserva del primer intento; <id>.lock2, .lock3… los de los reintentos
#   <id>.cancelar   se pidió cancelarlo
#   <id>.fin        llegó a un estado final y ningún worker lo vuelve a mirar
#   <id>/intento-N/ dataset armado y corrida de Ultralytics de cada intento
# Así los workers eligen candidatos por los nombres de archivo y solo abren sus JSON.

# El id viaja en las URLs y arma nombres de archivo
ID_VALIDO = re.compile(r"^[0-9a-f]{12}$")

ESTADOS_FINALES = ("completado", "fallido", "cancelado")

# Un trabajo en ejecución renueva su "latido" cada pocos segundos en todas sus fases
# (armado del dataset, entrenamiento, validación, evaluación). Si pasa más que esto sin
# latido, se da por muerto a su worker: otro lo retoma, o la cancelación se aplica sin esperarlo.
LATIDO_MAXIMO_S = int(os.environ.get("LATIDO_MAXIMO_S", "600"))

# Si un trabajo deja tirado a su worker este número de veces (por ejemplo, porque lo
# mata por falta de memoria), no se reintenta más
MAX_INTENTOS = int(os.environ.get("MAX_INTENTOS", "2"))


class TrabajoPerdido(Exception):
    """El trabajo ya no es de este worker: lo dieron por muerto y otro lo retomó, o terminó."""


def _archivo(trabajo_id: str, extension: str) -> Optional[Path]:
    if not ID_VALIDO.match(trabajo_id or ""):
        return None
    return TRABAJOS_DIR / f"{trabajo_id}.{extension}"


def _extension_lock(intento: int) -> str:
    return "lock" if intento <= 1 else f"lock{intento}"


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def carpeta_intento(trabajo_id: str, intento: int) -> Path:
    return (TRABAJOS_DIR / trabajo_id / f"intento-{intento}").resolve()


def cancelacion_pedida(trabajo_id: str) -> bool:
    """La señal de cancelación es un archivo aparte: el JSON del trabajo lo reescribe el worker."""
    marca = _archivo(trabajo_id, "cancelar")
    return marca is not None and marca.exists()


def _con_cancelacion(trabajo: Dict) -> Dict:
    if trabajo.get("estado") in ("pendiente", "ejecutando"):
        trabajo["cancelacion_pedida"] = cancelacion_pedida(trabajo.get("id", ""))
    return trabajo


def _escribir_json_atomico(ruta: Path, data: Dict) -> None:
    """
    Escribe el JSON en un temporal y lo renombra encima del original. El renombrado es
    atómico: quien lea el archivo (la API mandando el progreso, otro worker buscando
    pendientes) ve la versión anterior completa o la nueva completa, nunca una a medias.
    """
    temporal = ruta.with_name(f".{ruta.name}.{uuid.uuid4().hex}.tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    # En Windows el renombrado falla si otro proceso tiene el destino abierto en ese
    # instante; se reintenta. En Linux (Docker) reemplaza aunque esté abierto.
    for intento in range(50):
        try:
            os.replace(temporal, ruta)
            return
        except PermissionError:
            if intento == 49:
                raise
            time.sleep(0.01)


def _leer(ruta: Path) -> Optional[Dict]:
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def encolar_trabajo(
    datasets: List[str],
    epocas: int = 50,
    imgsz: int = 640,
    pesos_base: str = "yolov8n.pt",
    fraccion_validacion: float = 0.25,
) -> Dict:
    TRABAJOS_DIR.mkdir(parents=True, exist_ok=True)
    trabajo_id = uuid.uuid4().hex[:12]
    archivo_trabajo = TRABAJOS_DIR / f"{trabajo_id}.json"

    trabajo = {
        "id": trabajo_id,
        "estado": "pendiente",  # pendiente, ejecutando, completado, fallido, cancelado
        # Con microsegundos: es la clave de orden de la cola, y con precisión de segundos
        # varios trabajos encolados juntos empataban y se tomaba primero el más nuevo
        "fecha_creacion": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "datasets": datasets,
        "epocas": epocas,
        "imgsz": imgsz,
        "pesos_base": pesos_base,
        "fraccion_validacion": fraccion_validacion,
        "progreso_epocas": 0,
        "metricas": {},
        "version_generada": None,
        "error": None
    }

    _escribir_json_atomico(archivo_trabajo, trabajo)

    return trabajo


def listar_trabajos() -> List[Dict]:
    """Todos los trabajos, para la web. Los workers no usan esto: ver reclamar_siguiente_pendiente."""
    if not TRABAJOS_DIR.is_dir():
        return []

    res = []
    for f in sorted(TRABAJOS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        trabajo = _leer(f)
        if trabajo is not None:
            res.append(_con_cancelacion(trabajo))
    return res


def obtener_trabajo(trabajo_id: str) -> Optional[Dict]:
    archivo = _archivo(trabajo_id, "json")
    trabajo = _leer(archivo) if archivo is not None else None
    return _con_cancelacion(trabajo) if trabajo is not None else None


def actualizar_trabajo(trabajo_id: str, **kwargs) -> Optional[Dict]:
    archivo = _archivo(trabajo_id, "json")
    if archivo is None or not archivo.is_file():
        return None

    with open(archivo, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.update(kwargs)

    _escribir_json_atomico(archivo, data)

    return data


def verificar_que_es_mio(trabajo_id: str, worker: str, intento: int) -> None:
    """
    Lanza TrabajoPerdido si el trabajo ya no es de este worker en este intento, o si
    terminó. Así un worker que dieron por muerto (por ejemplo, porque estuvo pausado)
    no pisa al que lo retomó.
    """
    actual = obtener_trabajo(trabajo_id)
    if (
        actual is None
        or actual.get("estado") in ESTADOS_FINALES
        or actual.get("worker") != worker
        or actual.get("intentos", 1) != intento
    ):
        raise TrabajoPerdido()


def actualizar_si_es_mio(trabajo_id: str, worker: str, intento: int, **kwargs) -> Optional[Dict]:
    verificar_que_es_mio(trabajo_id, worker, intento)
    return actualizar_trabajo(trabajo_id, **kwargs)


def finalizar_trabajo(trabajo_id: str, estado: str, **kwargs) -> Optional[Dict]:
    """Deja el trabajo en un estado final y lo marca con .fin para que ningún worker lo vuelva a mirar."""
    trabajo = actualizar_trabajo(trabajo_id, estado=estado, fecha_fin=ahora_iso(), **kwargs)
    if trabajo is not None:
        _archivo(trabajo_id, "fin").touch()
    return trabajo


def finalizar_si_es_mio(trabajo_id: str, worker: str, intento: int, estado: str, **kwargs) -> Optional[Dict]:
    verificar_que_es_mio(trabajo_id, worker, intento)
    return finalizar_trabajo(trabajo_id, estado, **kwargs)


def reclamar_trabajo(trabajo_id: str, worker: str, intento: int = 1) -> bool:
    """
    Intenta quedarse con un intento de un trabajo creando su archivo de reserva en modo
    exclusivo (O_EXCL): el sistema operativo garantiza que, si varios workers lo intentan
    a la vez, solo uno lo crea. Retorna True si este worker lo reclamó.
    """
    lock = _archivo(trabajo_id, _extension_lock(intento))
    if lock is None:
        return False
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(worker)
    return True


def _segundos_sin_latido(trabajo: Dict) -> float:
    """
    Desde el último latido. Un trabajo reservado que todavía no escribió nada no tiene
    latido: se usa la hora de su última reserva.
    """
    if trabajo.get("latido"):
        ultimo = datetime.fromisoformat(trabajo["latido"]).timestamp()
    else:
        locks = [_archivo(trabajo["id"], _extension_lock(i)) for i in range(1, trabajo.get("intentos", 1) + 2)]
        tiempos = [l.stat().st_mtime for l in locks if l is not None and l.exists()]
        if not tiempos:
            return 0.0
        ultimo = max(tiempos)
    return time.time() - ultimo


def _nombres_por_tipo() -> Dict[str, set]:
    """Ids de los trabajos según qué archivos tienen, con un solo listado del directorio."""
    tipos: Dict[str, set] = {"json": set(), "lock": set(), "fin": set()}
    if not TRABAJOS_DIR.is_dir():
        return tipos
    for entrada in os.scandir(TRABAJOS_DIR):
        if entrada.name.startswith(".") or not entrada.is_file():
            continue
        trabajo_id, _, extension = entrada.name.partition(".")
        if extension.startswith("lock"):
            tipos["lock"].add(trabajo_id)
        elif extension in tipos:
            tipos[extension].add(trabajo_id)
    return tipos


def _retomar_abandonado(worker: str, candidatos: set) -> Optional[Dict]:
    """
    Busca, entre los trabajos reservados que no terminaron, uno cuyo worker dejó de dar
    señales, y lo retoma desde cero en un intento nuevo. Si ya agotó los intentos, lo da
    por fallido. La reserva de cada intento es exclusiva: si dos workers ven el mismo
    abandonado, solo uno lo retoma.
    """
    for trabajo_id in sorted(candidatos):
        trabajo = obtener_trabajo(trabajo_id)
        if trabajo is None:
            continue
        if trabajo["estado"] in ESTADOS_FINALES:
            # Terminó antes de que existiera la marca .fin: se la agrega una sola vez
            _archivo(trabajo_id, "fin").touch()
            continue
        inactivo = _segundos_sin_latido(trabajo)
        if inactivo <= LATIDO_MAXIMO_S:
            continue

        intento = trabajo.get("intentos", 1) + 1
        if not reclamar_trabajo(trabajo_id, worker, intento):
            continue
        if intento > MAX_INTENTOS:
            finalizar_trabajo(
                trabajo_id, "fallido",
                error=f"Su worker dejó de responder {intento - 1} veces (¿se quedó sin memoria?). No se reintenta más.",
            )
            continue
        print(f"[COLA] {worker} retoma {trabajo_id}: su worker anterior no da señales hace "
              f"{round(inactivo)} s (intento {intento} de {MAX_INTENTOS}).")
        return actualizar_trabajo(
            trabajo_id, estado="ejecutando", worker=worker, intentos=intento, latido=ahora_iso(),
            progreso=None, progreso_epocas=0, metricas={},
        )
    return None


def reclamar_siguiente_pendiente(worker: str) -> Optional[Dict]:
    """
    Toma un trabajo y lo marca como "ejecutando": primero uno abandonado por un worker que
    murió (estaba antes en la cola), si no el pendiente más antiguo. Solo abre los JSON de
    los candidatos: los terminados tienen .fin y los demás se distinguen por sus reservas.
    """
    tipos = _nombres_por_tipo()
    abiertos = tipos["json"] - tipos["fin"]

    retomado = _retomar_abandonado(worker, abiertos & tipos["lock"])
    if retomado:
        return retomado

    pendientes = [t for t in (obtener_trabajo(i) for i in abiertos - tipos["lock"]) if t and t["estado"] == "pendiente"]
    for trabajo in sorted(pendientes, key=lambda x: x["fecha_creacion"]):
        if reclamar_trabajo(trabajo["id"], worker):
            return actualizar_trabajo(trabajo["id"], estado="ejecutando", worker=worker, intentos=1, latido=ahora_iso())
    return None


def pedir_cancelacion(trabajo_id: str) -> Optional[Dict]:
    """
    Cancela un trabajo pendiente o en ejecución. Devuelve el trabajo actualizado,
    o None si no existe. Si ya terminó, lo devuelve sin cambios.

    - Pendiente: se reclama con la misma reserva que usan los workers, así ninguno
      puede tomarlo a la vez, y queda cancelado en el momento.
    - En ejecución: se crea la marca .cancelar y el worker corta en el próximo
      lote. Si el worker no da señales hace rato (murió), se cancela sin esperarlo.
    """
    trabajo = obtener_trabajo(trabajo_id)
    if trabajo is None or trabajo["estado"] in ESTADOS_FINALES:
        return trabajo

    if trabajo["estado"] == "pendiente":
        if reclamar_trabajo(trabajo_id, "cancelado"):
            return finalizar_trabajo(trabajo_id, "cancelado", error="Cancelado antes de empezar.")
        # Un worker lo reclamó justo ahora: se decide con lo que haya escrito desde entonces
        trabajo = obtener_trabajo(trabajo_id)
        if trabajo is None or trabajo["estado"] in ESTADOS_FINALES:
            return trabajo

    # La marca la ve el worker al empezar cada fase y en cada lote. Si todavía figura
    # como pendiente es porque el worker lo reservó y no llegó a escribir: va a cortar
    # apenas arranque, así que no hay que forzar nada.
    _archivo(trabajo_id, "cancelar").touch()
    if trabajo["estado"] == "ejecutando" and _segundos_sin_latido(trabajo) > LATIDO_MAXIMO_S:
        return _con_cancelacion(finalizar_trabajo(
            trabajo_id, "cancelado",
            error="Cancelado sin respuesta del worker: no daba señales de vida, probablemente se detuvo.",
        ))
    return obtener_trabajo(trabajo_id)
