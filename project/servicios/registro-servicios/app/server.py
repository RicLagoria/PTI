"""
registro-servicios: descubrimiento de servicios simplificado (Entrega 4 de PDC).

Cada instancia de un servicio se anuncia sola al arrancar (PUT) y renueva el
anuncio con un latido periódico, que es el mismo PUT. Si deja de latir durante
más de REGISTRO_TTL_S segundos, se la da por caída y deja de listarse, sin que
nadie tenga que borrarla. Los consumidores preguntan por un nombre lógico
(GET /servicios/ia-inferencia) y reciben las URL de las instancias vivas.

Es un registro en memoria: si se reinicia, en un intervalo de latido las
instancias vuelven a anunciarse solas. Por eso no necesita base de datos.
"""
import os
import re
import threading
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Path, Response
from pydantic import BaseModel, Field

TTL_S = float(os.environ.get("REGISTRO_TTL_S", "15"))
_PATRON_NOMBRE = r"^[a-z0-9][a-z0-9-]{0,62}$"

app = FastAPI(
    title="AgroVision - Registro de servicios",
    version="1.0.0",
    description="Descubrimiento de servicios por anuncio y latido, con vencimiento por TTL.",
)


class Anuncio(BaseModel):
    url: str = Field(..., pattern=r"^https?://", examples=["http://172.18.0.5:8001"])
    metadatos: Dict[str, str] = Field(default_factory=dict, examples=[{"version": "1.1.0"}])


class Instancia(BaseModel):
    id: str
    url: str
    metadatos: Dict[str, str]
    ultimo_latido: float = Field(..., description="Época UNIX del último anuncio recibido.")
    vence_en_s: float = Field(..., description="Segundos que quedan antes de darla por caída.")


class Servicio(BaseModel):
    nombre: str
    instancias: List[Instancia]


# {nombre: {instancia_id: {"url", "metadatos", "ultimo_latido"}}}
_registro: Dict[str, Dict[str, dict]] = {}
_candado = threading.Lock()


def _vivas(nombre: str, ahora: Optional[float] = None) -> List[Instancia]:
    """Instancias con latido vigente; de paso purga las vencidas."""
    ahora = ahora if ahora is not None else time.time()
    instancias = _registro.get(nombre, {})
    for vencida in [i for i, d in instancias.items() if ahora - d["ultimo_latido"] > TTL_S]:
        del instancias[vencida]
    return [
        Instancia(id=i, url=d["url"], metadatos=d["metadatos"], ultimo_latido=d["ultimo_latido"],
                  vence_en_s=round(TTL_S - (ahora - d["ultimo_latido"]), 2))
        for i, d in sorted(instancias.items())
    ]


@app.get("/salud")
def salud():
    return {"estado": "ok", "servicio": "registro-servicios", "ttl_s": TTL_S}


@app.put("/servicios/{nombre}/instancias/{instancia_id}", response_model=Instancia)
def anunciar(
    anuncio: Anuncio,
    nombre: str = Path(..., pattern=_PATRON_NOMBRE),
    instancia_id: str = Path(..., pattern=_PATRON_NOMBRE),
):
    """
    Alta o latido de una instancia. Es idempotente: la primera llamada la
    registra y las siguientes renuevan su vencimiento (y actualizan la URL si cambió).
    """
    with _candado:
        _registro.setdefault(nombre, {})[instancia_id] = {
            "url": anuncio.url.rstrip("/"),
            "metadatos": anuncio.metadatos,
            "ultimo_latido": time.time(),
        }
        return next(i for i in _vivas(nombre) if i.id == instancia_id)


@app.delete("/servicios/{nombre}/instancias/{instancia_id}", status_code=204)
def retirar(nombre: str, instancia_id: str):
    """Baja ordenada (al apagarse). Si la instancia ya no estaba, también responde 204."""
    with _candado:
        _registro.get(nombre, {}).pop(instancia_id, None)
    return Response(status_code=204)


@app.get("/servicios/{nombre}", response_model=Servicio)
def consultar(nombre: str):
    """Instancias vivas del servicio. La lista puede venir vacía: decide el consumidor."""
    with _candado:
        return Servicio(nombre=nombre, instancias=_vivas(nombre))


@app.get("/servicios", response_model=List[Servicio])
def listar():
    """Todos los servicios con al menos una instancia viva."""
    with _candado:
        servicios = [Servicio(nombre=n, instancias=_vivas(n)) for n in sorted(_registro)]
    return [s for s in servicios if s.instancias]
