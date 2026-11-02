"""
Elección de CPU o GPU para entrenar, y qué hay disponible donde corre esto.

Entrenar en CPU con unos cientos de imágenes lleva horas; con una GPU NVIDIA
decente, minutos. Por eso el entrenamiento se pide con `dispositivo`, y acá se
traduce a lo que espera Ultralytics (`device="cpu"` o el índice de la GPU) junto
con un tamaño de lote acorde: en CPU el lote chico es lo único que entra en RAM,
en GPU un lote chico desaprovecha la placa.

Hacen falta tres cosas para que la GPU funcione, y las tres fallan distinto:

1. La placa y su driver en la máquina — `nvidia-smi` la tiene que ver.
2. Un torch compilado con CUDA. La imagen se construye por defecto con las
   ruedas `+cpu` (sin eso suma varios GB de librerías CUDA), así que para
   entrenar en GPU hay que construirla con VARIANTE_TORCH=cu128; ver el
   Dockerfile y despliegue/compose.ia.gpu.yml.
3. Que el contenedor tenga acceso al dispositivo (nvidia-container-toolkit en el
   host y la reserva de GPU en el compose).

`describir()` distingue los tres casos para poder decirle a la persona cuál le
falta, en vez de "no hay GPU". El worker llama `resolver()` antes de entrenar: si
se pidió GPU y no está, el trabajo falla en el momento con ese detalle, en vez de
entrenar en CPU durante horas sin que nadie se dé cuenta.
"""
import os
from typing import Any, Dict, Optional, Tuple

DISPOSITIVOS = ("cpu", "gpu")
DISPOSITIVO_POR_DEFECTO = "cpu"

# Imágenes por lote. En CPU manda la RAM (2 era el valor con el que se entrenó
# train-3); en GPU, la VRAM: 16 a 640 px entra con holgura en una placa de 8 GB.
LOTE_CPU = int(os.environ.get("LOTE_CPU", "2"))
LOTE_GPU = int(os.environ.get("LOTE_GPU", "16"))


class SinGPU(Exception):
    """Se pidió entrenar en GPU y no se puede. El mensaje dice qué falta."""


def _torch():
    """
    torch tarda segundos en importarse y no se necesita para casi ningún
    endpoint, así que se importa recién cuando se pregunta por los dispositivos.
    """
    try:
        import torch
        return torch
    except ImportError:
        return None


def describir() -> Dict[str, Any]:
    """
    Qué dispositivos ve este proceso. Lo usa la API para que entrenador-web
    pueda ofrecer o no la GPU, y explicar por qué cuando no.

    Ojo: lo que ve la API, no el worker. Son contenedores distintos (la GPU se
    le reserva al worker), aunque en los dos compose corran en la misma máquina
    y desde la misma imagen, así que alcanza para mostrarlo en la web. La
    palabra final la tiene resolver() en el worker.
    """
    torch = _torch()
    if torch is None:
        return {
            "gpu_disponible": False,
            "motivo": "Este servicio no tiene torch instalado.",
            "torch_con_cuda": False,
            "gpus": [],
            "lote_cpu": LOTE_CPU,
            "lote_gpu": LOTE_GPU,
        }

    # None en las ruedas +cpu: el torch instalado no sabe hablar con una GPU
    cuda_de_torch = getattr(torch.version, "cuda", None)
    disponible = bool(cuda_de_torch) and torch.cuda.is_available()

    gpus = []
    if disponible:
        for i in range(torch.cuda.device_count()):
            propiedades = torch.cuda.get_device_properties(i)
            gpus.append({
                "indice": i,
                "nombre": propiedades.name,
                "memoria_gb": round(propiedades.total_memory / (1024 ** 3), 1),
            })

    if disponible:
        motivo = None
    elif not cuda_de_torch:
        motivo = (
            "La imagen se construyó con las ruedas de torch para CPU. Para entrenar en GPU hay "
            "que construirla con VARIANTE_TORCH=cu128 y levantar el worker con "
            "despliegue/compose.ia.gpu.yml."
        )
    else:
        motivo = (
            "torch tiene CUDA pero no ve ninguna GPU: falta el acceso al dispositivo desde el "
            "contenedor (nvidia-container-toolkit en el host y la reserva de GPU del compose), "
            "o la máquina no tiene una placa NVIDIA."
        )

    return {
        "gpu_disponible": disponible,
        "motivo": motivo,
        "torch_con_cuda": bool(cuda_de_torch),
        "cuda": cuda_de_torch,
        "gpus": gpus,
        "lote_cpu": LOTE_CPU,
        "lote_gpu": LOTE_GPU,
    }


def resolver(dispositivo: str) -> Tuple[Any, int]:
    """
    Traduce el dispositivo pedido a (device, batch) para model.train() y
    model.val(). Lanza SinGPU si se pidió "gpu" y no hay.
    """
    if dispositivo not in DISPOSITIVOS:
        raise ValueError(f"Dispositivo desconocido: {dispositivo!r}. Los válidos son {list(DISPOSITIVOS)}.")
    if dispositivo == "cpu":
        return "cpu", LOTE_CPU

    info = describir()
    if not info["gpu_disponible"]:
        raise SinGPU(f"Se pidió entrenar en GPU pero no está disponible. {info['motivo']}")
    # Ultralytics toma el índice de la placa, no el string "gpu"
    return info["gpus"][0]["indice"], LOTE_GPU


def etiqueta(dispositivo: str) -> Optional[str]:
    """Nombre de la placa para los logs, o None si se entrena en CPU."""
    if dispositivo != "gpu":
        return None
    gpus = describir()["gpus"]
    return gpus[0]["nombre"] if gpus else None
