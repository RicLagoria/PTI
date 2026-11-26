"""
Anuncio automático en registro-servicios (Entrega 4 de PDC).

Si REGISTRO_URL está definida, la instancia se registra al arrancar, repite el
anuncio cada REGISTRO_INTERVALO_S segundos (latido) y se da de baja al
apagarse. Si no está definida, no hace nada: el servicio funciona igual que
antes y los consumidores usan su URL fija.

La URL que se anuncia sale de URL_ANUNCIADA; si falta, se arma con la IP con la
que esta máquina llega al registro. Así cada réplica (docker compose --scale)
anuncia su propia dirección sin configurar nada por réplica.
"""
import os
import socket
import threading
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx

NOMBRE_SERVICIO = "ia-inferencia"
REGISTRO_URL = os.environ.get("REGISTRO_URL", "").rstrip("/")
INTERVALO_S = float(os.environ.get("REGISTRO_INTERVALO_S", "5"))
PUERTO = int(os.environ.get("PUERTO", "8001"))


def _ip_hacia(url: str) -> str:
    """IP local de la interfaz que sale hacia `url` (no envía paquetes: UDP sin datos)."""
    destino = urlparse(url)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((destino.hostname, destino.port or 80))
        return s.getsockname()[0]


class Anunciador:
    def __init__(self, metadatos: Optional[Dict[str, str]] = None):
        self.metadatos = metadatos or {}
        self.url = os.environ.get("URL_ANUNCIADA", "").rstrip("/")
        self.instancia_id = os.environ.get("INSTANCIA_ID", "")
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None

    @property
    def activo(self) -> bool:
        return bool(REGISTRO_URL)

    def _endpoint(self) -> str:
        return f"{REGISTRO_URL}/servicios/{NOMBRE_SERVICIO}/instancias/{self.instancia_id}"

    def _anunciar(self):
        httpx.put(self._endpoint(), json={"url": self.url, "metadatos": self.metadatos}, timeout=3)

    def _latir(self):
        while not self._parar.wait(INTERVALO_S):
            try:
                self._anunciar()
            except Exception as e:  # el registro caído no debe tirar al servicio
                print(f"[REGISTRO] No se pudo renovar el anuncio: {e}")

    def iniciar(self):
        if not self.activo:
            print("[REGISTRO] REGISTRO_URL vacía: sin anuncio, se usa la URL fija.")
            return
        if not self.url:
            self.url = f"http://{_ip_hacia(REGISTRO_URL)}:{PUERTO}"
        if not self.instancia_id:
            self.instancia_id = f"{socket.gethostname()}-{PUERTO}".lower()[:63]
        try:
            self._anunciar()
            print(f"[REGISTRO] Anunciado {NOMBRE_SERVICIO}/{self.instancia_id} en {self.url}")
        except Exception as e:
            print(f"[REGISTRO] Registro no disponible ({e}); se reintenta con cada latido.")
        self._hilo = threading.Thread(target=self._latir, daemon=True)
        self._hilo.start()

    def detener(self):
        if not self.activo:
            return
        self._parar.set()
        try:
            httpx.delete(self._endpoint(), timeout=3)
            print(f"[REGISTRO] Baja de {NOMBRE_SERVICIO}/{self.instancia_id}")
        except Exception:
            pass  # si no llega, el TTL del registro la vence igual
