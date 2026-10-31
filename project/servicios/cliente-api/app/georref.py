import math
from typing import Any, Dict, List, Optional, Tuple

try:
    from py_geo.geo import GeoHandler
except ImportError:
    import sys
    from pathlib import Path
    ruta_compartido = Path(__file__).resolve().parent.parent.parent.parent / "compartido" / "py-geo"
    if str(ruta_compartido) not in sys.path:
        sys.path.insert(0, str(ruta_compartido))
    from py_geo.geo import GeoHandler


# Radio medio de la Tierra (esfera de igual superficie que el WGS84)
RADIO_TIERRA_M = 6371008.8


def area_m2(contorno: List[Tuple[float, float]]) -> Optional[float]:
    """
    Superficie en metros cuadrados de un contorno dado como [(lat, lon), ...].

    Sobre la base la hace PostGIS con ST_Area(contorno::geography) (ver
    datos.obtener_detecciones), pero en un análisis en vivo las detecciones van
    al navegador antes de leerse de vuelta: hay que calcularla acá para que el
    mapa muestre la superficie mientras el análisis corre.

    Proyecta los vértices a un plano tangente en el centro del contorno y aplica
    la fórmula del área de Gauss. Una mancha de maleza mide metros o decenas de
    metros, escala en la que esa aproximación se aparta menos del 0,1 % de la
    superficie sobre el elipsoide: alcanza de sobra para un informe agronómico.
    """
    if len(contorno) < 3:
        return None

    lat_media = math.radians(sum(lat for lat, _ in contorno) / len(contorno))
    escala_lon = math.cos(lat_media) * math.radians(RADIO_TIERRA_M)
    escala_lat = math.radians(RADIO_TIERRA_M)
    puntos = [(lon * escala_lon, lat * escala_lat) for lat, lon in contorno]

    doble_area = 0.0
    for (x1, y1), (x2, y2) in zip(puntos, puntos[1:] + puntos[:1]):
        doble_area += x1 * y2 - x2 * y1
    return round(abs(doble_area) / 2.0, 2)


def traducir_deteccion(
    det_local: Dict[str, Any],
    celda_meta: Dict[str, Any],
    geo: GeoHandler
) -> Dict[str, Any]:
    """
    Traduce una detección con coordenadas locales de tesela a:
    - box_global_px: coordenadas absolutas en píxeles del ortomosaico.
    - gps_centro: coordenadas lat/lon precisas en WGS84 calculadas sobre el centro de la caja.

    Y, si el modelo activo es de segmentación y la detección trae contorno:
    - contorno_global_px: el mismo contorno en píxeles del ortomosaico (lo usa
      el informe en PDF, que dibuja sobre la imagen).
    - contorno: el contorno en WGS84 como [[lat, lon], ...]. Ese orden es el que
      espera Leaflet, que es quien lo dibuja; la base lo guarda al revés (PostGIS
      usa lon/lat), ver datos.insertar_detecciones.

    Acá es donde el sistema vuelve a ser geográfico: ia-inferencia devolvió
    píxeles de una tesela sin saber de qué parte del campo son.
    """
    offset_x = celda_meta["x"]
    offset_y = celda_meta["y"]
    # La celda pudo leerse reducida (análisis a escala gruesa, ver GeoHandler),
    # y entonces el modelo trabajó sobre una imagen más chica que el pedazo de
    # raster que representa: hay que deshacer esa reducción antes de correr la
    # detección a su lugar. A escala 1 los dos factores son 1.0.
    factor_x = celda_meta.get("factor_x", 1.0)
    factor_y = celda_meta.get("factor_y", 1.0)

    lx1, ly1, lx2, ly2 = det_local["box_local"]
    gx1 = offset_x + lx1 * factor_x
    gy1 = offset_y + ly1 * factor_y
    gx2 = offset_x + lx2 * factor_x
    gy2 = offset_y + ly2 * factor_y

    # Centro preciso de la caja detectada
    centro_x = (gx1 + gx2) / 2.0
    centro_y = (gy1 + gy2) / 2.0

    lat, lon = geo.pixel_global_a_latlon(centro_x, centro_y)

    deteccion = {
        "fila": celda_meta["fila"],
        "col": celda_meta["col"],
        "clase": det_local["clase"],
        "confianza": det_local["confianza"],
        "box_local": [round(v, 1) for v in [lx1, ly1, lx2, ly2]],
        "box_global_px": [round(v, 1) for v in [gx1, gy1, gx2, gy2]],
        "gps_centro": {
            "lat": lat,
            "lon": lon
        }
    }

    contorno_local: List[List[float]] = det_local.get("contorno_local") or []
    if len(contorno_local) >= 3:
        globales = [(offset_x + x * factor_x, offset_y + y * factor_y) for x, y in contorno_local]
        # Una sola reproyección para todos los vértices, no una por vértice
        vertices = geo.pixeles_globales_a_latlon(globales)
        deteccion["contorno_global_px"] = [[round(x, 1), round(y, 1)] for x, y in globales]
        deteccion["contorno"] = [[lat_v, lon_v] for lat_v, lon_v in vertices]
        deteccion["area_m2"] = area_m2(vertices)

    return deteccion
