from typing import Any, Dict, List

try:
    from py_geo.geo import GeoHandler
except ImportError:
    import sys
    from pathlib import Path
    ruta_compartido = Path(__file__).resolve().parent.parent.parent.parent / "compartido" / "py-geo"
    if str(ruta_compartido) not in sys.path:
        sys.path.insert(0, str(ruta_compartido))
    from py_geo.geo import GeoHandler


def traducir_deteccion(
    det_local: Dict[str, Any],
    celda_meta: Dict[str, Any],
    geo: GeoHandler
) -> Dict[str, Any]:
    """
    Traduce una detección con coordenadas locales de tesela a:
    - box_global_px: coordenadas absolutas en píxeles del ortomosaico.
    - gps_centro: coordenadas lat/lon precisas en WGS84 calculadas sobre el centro de la caja.
    """
    offset_x = celda_meta["x"]
    offset_y = celda_meta["y"]

    lx1, ly1, lx2, ly2 = det_local["box_local"]
    gx1 = offset_x + lx1
    gy1 = offset_y + ly1
    gx2 = offset_x + lx2
    gy2 = offset_y + ly2

    # Centro preciso de la caja detectada
    centro_x = (gx1 + gx2) / 2.0
    centro_y = (gy1 + gy2) / 2.0

    lat, lon = geo.pixel_global_a_latlon(centro_x, centro_y)

    return {
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
