import os
from typing import Any, Dict, List, Tuple
import httpx

IA_INFERENCIA_URL = os.environ.get("IA_INFERENCIA_URL", "http://localhost:8001").rstrip("/")


class ClienteIA:
    def __init__(self, base_url: str = IA_INFERENCIA_URL, timeout: float = 60.0):
        self.base_url = base_url
        self.timeout = timeout

    def obtener_modelo(self) -> Dict[str, Any]:
        """Consulta metadatos del modelo activo a ia-inferencia (GET /modelo)."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(f"{self.base_url}/modelo")
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
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(
                    f"{self.base_url}/detectar",
                    params={"conf": conf},
                    files=files
                )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("detecciones", [])
                else:
                    print(f"[ERROR] ia-inferencia retornó estado {res.status_code}: {res.text}")
                    return []
        except Exception as e:
            print(f"[ERROR] Falló la petición a ia-inferencia ({self.base_url}/detectar): {e}")
            raise

