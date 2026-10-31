import math
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform as transformar_coordenadas
from rasterio.windows import Window

CRS_WGS84 = CRS.from_epsg(4326)


class GeoHandler:
    """
    Recorre un ortomosaico en celdas del tamaño que espera el modelo.

    `escala` separa dos cosas que no son la misma: cuánto campo abarca una celda
    y cuántos píxeles recibe el modelo. Con escala 1 la celda son 640 px del
    raster leídos tal cual, que a 3,3 cm/px son unos 21 m: una mancha más grande
    no entra entera en la imagen y el modelo aprende a cortarla. Con escala 4 la
    celda son 2560 px del raster reducidos a los mismos 640, o sea el mismo
    encuadre con cuatro veces más campo: la cámara se aleja.

    Alejarse sale más barato, no más caro: un COG trae resúmenes a media, cuarta
    y octava resolución, y `out_shape` hace que rasterio lea del resumen que
    corresponde en vez del raster completo. A escala 4 hay 16 veces menos celdas
    y cada una cuesta lo mismo que una de escala 1.
    """

    def __init__(self, ruta_tif: str, tamano_tile: int = 640, escala: int = 1):
        self.ruta_tif = ruta_tif
        self.tamano_tile = tamano_tile
        self.escala = max(1, int(escala))
        # Lo que mide la celda en píxeles del raster, antes de reducirla
        self.tamano_celda = tamano_tile * self.escala
        self.src = rasterio.open(ruta_tif)
        self.ancho_total = self.src.width
        self.alto_total = self.src.height
        self.transform = self.src.transform
        self.filas = math.ceil(self.alto_total / self.tamano_celda)
        self.columnas = math.ceil(self.ancho_total / self.tamano_celda)

    def tamano_leido(self, ancho: int, alto: int) -> Tuple[int, int]:
        """
        Cuánto mide la celda una vez reducida, que es lo que recibe el modelo.

        Las celdas del borde del raster salen más chicas que las demás, así que
        el factor de reducción real no es exactamente `escala` y hay que
        calcularlo contra lo que efectivamente se leyó. Lo usan
        `obtener_lista_cuadrantes`, para anotarlo en cada celda, y
        `leer_tile_filtrado`, para pedirle ese tamaño a rasterio.
        """
        if self.escala == 1:
            return ancho, alto
        return max(1, ancho // self.escala), max(1, alto // self.escala)

    def obtener_lista_cuadrantes(self, cuadrante: Optional[int] = None) -> List[Dict]:
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
            y = r * self.tamano_celda
            alto = min(self.tamano_celda, self.alto_total - y)
            for c_local, c in enumerate(c_rango):
                x = c * self.tamano_celda
                ancho = min(self.tamano_celda, self.ancho_total - x)
                lon, lat = rasterio.transform.xy(self.transform, y + (alto // 2), x + (ancho // 2))
                ancho_leido, alto_leido = self.tamano_leido(ancho, alto)
                lista_celdas.append({
                    "fila": r_local,
                    "col": c_local,
                    "x": x,
                    "y": y,
                    # En píxeles del raster: lo que abarca la celda
                    "ancho": ancho,
                    "alto": alto,
                    # Por cuánto hay que multiplicar una coordenada que devuelve
                    # el modelo para volver a píxeles del raster. Es 1.0 a escala
                    # 1, y en una celda del borde no es exactamente la escala.
                    "factor_x": ancho / ancho_leido,
                    "factor_y": alto / alto_leido,
                    "lat": lat,
                    "lon": lon
                })

        # El transform entrega coordenadas en el CRS del raster (p. ej. metros UTM);
        # el visor necesita grados WGS84
        if lista_celdas and self.src.crs != CRS_WGS84:
            lons, lats = transformar_coordenadas(
                self.src.crs, CRS_WGS84,
                [c["lon"] for c in lista_celdas],
                [c["lat"] for c in lista_celdas]
            )
            for celda, lon, lat in zip(lista_celdas, lons, lats):
                celda["lon"] = lon
                celda["lat"] = lat

        return lista_celdas

    def pixel_global_a_latlon(self, x_px: float, y_px: float) -> Tuple[float, float]:
        """Convierte una coordenada en píxeles globales a (latitud, longitud) en WGS84."""
        lon, lat = rasterio.transform.xy(self.transform, y_px, x_px)
        if self.src.crs != CRS_WGS84:
            lons, lats = transformar_coordenadas(self.src.crs, CRS_WGS84, [lon], [lat])
            return lats[0], lons[0]
        return lat, lon

    def pixeles_globales_a_latlon(
        self, puntos: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """
        Igual que pixel_global_a_latlon pero para varios puntos de una vez, con
        una sola reproyección para todos. Es lo que hace falta al convertir el
        contorno de una detección: son decenas de vértices por detección y
        reproyectar de a uno multiplica por esa cantidad el costo de un análisis.
        """
        if not puntos:
            return []
        filas = [y for _, y in puntos]
        columnas = [x for x, _ in puntos]
        lons, lats = rasterio.transform.xy(self.transform, filas, columnas)
        if self.src.crs != CRS_WGS84:
            lons, lats = transformar_coordenadas(self.src.crs, CRS_WGS84, list(lons), list(lats))
        return list(zip(lats, lons))

    def leer_tile_filtrado(
        self,
        x: int,
        y: int,
        ancho: int,
        alto: int,
        umbral_brillo: int = 15,
        umbral_desviacion: int = 8
    ) -> Optional[np.ndarray]:
        """
        Lee el bloque del disco, ya reducido al tamaño de entrada del modelo, y
        descarta partes vacías/negras. Retorna None si la celda es borde negro o
        plano, evitando llamar a YOLO.

        `out_shape` es lo que hace barata la escala gruesa: rasterio resuelve la
        reducción contra el resumen del COG que más se acerque, así que leer una
        celda de 2560 px reducida a 640 cuesta lo mismo que leer una de 640, no
        dieciséis veces más.
        """
        ventana = Window(x, y, ancho, alto)
        num_bandas = min(self.src.count, 3)
        ancho_leido, alto_leido = self.tamano_leido(ancho, alto)
        bandas = self.src.read(
            list(range(1, num_bandas + 1)),
            window=ventana,
            out_shape=(num_bandas, alto_leido, ancho_leido),
        )

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
        if not self.src.closed:
            self.src.close()
