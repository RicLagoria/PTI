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

    def obtener_matriz_espacial(self, cuadrante=3):
        """
        Divide la imagen en 4 cuadrantes (2x2) y retorna la matriz del cuadrante seleccionado:
        - Cuadrante 1: Superior Izquierdo (NO)
        - Cuadrante 2: Superior Derecho (NE)
        - Cuadrante 3: Inferior Izquierdo (SO)
        - Cuadrante 4: Inferior Derecho (SE)
        Si cuadrante es None o fuera de rango (1-4), procesa la imagen completa.
        """
        mitad_filas = max(1, self.filas // 2)
        mitad_cols = max(1, self.columnas // 2)

        if cuadrante == 1:
            r_rango = range(0, mitad_filas)
            c_rango = range(0, mitad_cols)
        elif cuadrante == 2:
            r_rango = range(0, mitad_filas)
            c_rango = range(mitad_cols, self.columnas)
        elif cuadrante == 3:
            # Inferior Izquierdo: Desde la mitad de las filas hasta el final, columnas del inicio a la mitad
            r_rango = range(mitad_filas, self.filas)
            c_rango = range(0, mitad_cols)
        elif cuadrante == 4:
            r_rango = range(mitad_filas, self.filas)
            c_rango = range(mitad_cols, self.columnas)
        else:
            r_rango = range(self.filas)
            c_rango = range(self.columnas)

        matriz = []
        for r_local, r in enumerate(r_rango):
            fila = []
            y = r * self.tamano_tile
            alto = min(self.tamano_tile, self.alto_total - y)
            for c_local, c in enumerate(c_rango):
                x = c * self.tamano_tile
                ancho = min(self.tamano_tile, self.ancho_total - x)
                lon, lat = rasterio.transform.xy(self.transform, y + (alto // 2), x + (ancho // 2))
                fila.append({
                    "fila": r_local,
                    "col": c_local,
                    "bounds_px": (x, y, ancho, alto),
                    "gps_centro": (lat, lon)
                })
            matriz.append(fila)

        # Actualiza las dimensiones de trabajo a las celdas efectivamente seleccionadas
        self.filas = len(matriz)
        self.columnas = len(matriz[0]) if self.filas > 0 else 0
        return matriz

    def leer_tile(self, x, y, ancho, alto):
        ventana = Window(x, y, ancho, alto)
        num_bandas = min(self.src.count, 3)
        bandas = self.src.read(list(range(1, num_bandas + 1)), window=ventana)

        if num_bandas == 1:
            img = cv2.cvtColor(bandas[0], cv2.COLOR_GRAY2BGR)
        else:
            img = np.transpose(bandas, (1, 2, 0))

        if img.dtype != np.uint8:
            img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    def cerrar(self):
        self.src.close()