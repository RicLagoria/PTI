import math
import cv2
import numpy as np
import rasterio
from rasterio.windows import Window

class GeoHandler:
    def __init__(self, ruta_tif, tamano_tile=640):
        self.ruta_tif = ruta_tif
        self.tamano_tile = tamano_tile
        self.src = rasterio.open(ruta_tif)
        self.ancho_total = self.src.width
        self.alto_total = self.src.height
        self.transform = self.src.transform
        self.filas = math.ceil(self.alto_total / tamano_tile)
        self.columnas = math.ceil(self.ancho_total / tamano_tile)

    def obtener_lista_cuadrantes(self, cuadrante=None):
        mitad_filas = max(1, self.filas // 2)
        mitad_cols = max(1, self.columnas // 2)

        if cuadrante == 1:
            r_rango, c_rango = range(0, mitad_filas), range(0, mitad_cols)
        elif cuadrante == 2:
            r_rango, c_rango = range(0, mitad_filas), range(mitad_cols, self.columnas)
        elif cuadrante == 3:
            r_rango, c_rango = range(mitad_filas, self.filas), range(0, mitad_cols)
        elif cuadrante == 4:
            r_rango, c_rango = range(mitad_filas, self.filas), range(mitad_cols, self.columnas)
        else:
            r_rango, c_rango = range(self.filas), range(self.columnas)

        lista_celdas = []
        for r_local, r in enumerate(r_rango):
            y = r * self.tamano_tile
            alto = min(self.tamano_tile, self.alto_total - y)
            for c_local, c in enumerate(c_rango):
                x = c * self.tamano_tile
                ancho = min(self.tamano_tile, self.ancho_total - x)
                lon, lat = rasterio.transform.xy(self.transform, y + (alto // 2), x + (ancho // 2))
                lista_celdas.append({
                    "fila": r_local,
                    "col": c_local,
                    "x": x,
                    "y": y,
                    "ancho": ancho,
                    "alto": alto,
                    "lat": lat,
                    "lon": lon
                })
        return lista_celdas

    def leer_tile_filtrado(self, x, y, ancho, alto, umbral_brillo=15, umbral_desviacion=8):
        """
        Lee el bloque del disco y descarta partes vacías/negras.
        Retorna None si la celda es borde negro o plano, evitando llamar a YOLO.
        """
        ventana = Window(x, y, ancho, alto)
        num_bandas = min(self.src.count, 3)
        bandas = self.src.read(list(range(1, num_bandas + 1)), window=ventana)

        # Descarte 1: Si el promedio de píxeles es casi negro
        if bandas.mean() < umbral_brillo:
            return None

        # Descarte 2: Si no hay variación (ej. fondo monocolor sin textura vegetal)
        if bandas.std() < umbral_desviacion:
            return None

        if num_bandas == 1:
            img = cv2.cvtColor(bandas[0], cv2.COLOR_GRAY2BGR)
        else:
            img = np.transpose(bandas, (1, 2, 0))

        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    def cerrar(self):
        self.src.close()