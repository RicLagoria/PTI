import os
from typing import Any, Callable, Dict, List, Optional, Tuple
import httpx

import descubrimiento

NOMBRE_SERVICIO = "ia-inferencia"
IA_INFERENCIA_URL = os.environ.get("IA_INFERENCIA_URL", "http://localhost:8001").rstrip("/")


class ClienteIA:
    """
    Cliente de ia-inferencia. Con base_url fija habla siempre con esa URL. Sin
    ella, pregunta a registro-servicios qué instancias están vivas (ver
    descubrimiento.py) y, si una no responde, prueba con la siguiente.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 60.0):
        self.base_url_fija = base_url.rstrip("/") if base_url else None
        self.base_url = self.base_url_fija or IA_INFERENCIA_URL  # la última que respondió
        self.timeout = timeout

    def _candidatas(self) -> List[str]:
        if self.base_url_fija:
            return [self.base_url_fija]
        return descubrimiento.instancias(NOMBRE_SERVICIO, IA_INFERENCIA_URL)

    def _con_failover(self, pedido: Callable[[httpx.Client, str], httpx.Response]) -> httpx.Response:
        """
        Ejecuta `pedido` contra la primera instancia que responda. Solo pasa a la
        siguiente ante errores de transporte (conexión rechazada, caída, timeout):
        un 4xx/5xx es una respuesta válida del contrato y se devuelve tal cual.
        """
        ultimo_error: Optional[Exception] = None
        for url in self._candidatas():
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    respuesta = pedido(client, url)
                self.base_url = url
                return respuesta
            except httpx.TransportError as e:
                print(f"[AVISO] ia-inferencia en {url} no responde ({e}); pruebo otra instancia.")
                ultimo_error = e
                descubrimiento.invalidar(NOMBRE_SERVICIO)
        raise ultimo_error or httpx.ConnectError("No hay instancias de ia-inferencia.")

    def obtener_modelo(self) -> Dict[str, Any]:
        """Consulta metadatos del modelo activo a ia-inferencia (GET /modelo)."""
        try:
            res = self._con_failover(lambda client, url: client.get(f"{url}/modelo"))
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print(f"[AVISO] No se pudo consultar ia-inferencia ({self.base_url}/modelo): {e}")

        # Retorna valores por defecto si el servicio remoto aún no responde
        return {
            "version": "v1",
            "clases": ["maleza", "falla"],
            "imgsz": 640,
            "metricas": {},
            "disponible": False
        }

    def detectar_lote(
        self,
        lote_imagenes: List[Tuple[str, bytes]],
        conf: float = 0.10
    ) -> List[Dict[str, Any]]:
        """
        Envía un lote de teselas a ia-inferencia (POST /detectar?conf=...).
        lote_imagenes: [(tile_id, bytes_jpeg), ...]
        Retorna: [{"id": tile_id, "clase": str, "confianza": float, "box_local": [x1, y1, x2, y2]}]
        """
        if not lote_imagenes:
            return []

        files = []
        for tile_id, img_bytes in lote_imagenes:
            files.append((tile_id, (f"{tile_id}.jpg", img_bytes, "image/jpeg")))

        try:
            res = self._con_failover(lambda client, url: client.post(
                f"{url}/detectar",
                params={"conf": conf},
                files=files
            ))
            if res.status_code == 200:
                data = res.json()
                return data.get("detecciones", [])
            else:
                print(f"[ERROR] ia-inferencia retornó estado {res.status_code}: {res.text}")
                return []
        except Exception as e:
            print(f"[ERROR] Falló la petición a ia-inferencia ({self.base_url}/detectar): {e}")
            raise

