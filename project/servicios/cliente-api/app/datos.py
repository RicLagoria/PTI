"""
Capa de acceso a las tablas de ortomosaicos/analisis/detecciones (ver
02_analisis.sql). Reemplaza meta.json y detecciones.json: lo único que sigue
en disco es el .tif en sí (almacen.py), todo lo consultable vive acá.
"""
import csv
import io
import json
from typing import Callable, Dict, List, Optional, Tuple

from auth import conexion


# ==========================================================
# Ortomosaicos
# ==========================================================
_SELECT_ORTOMOSAICO = """
    SELECT o.id, o.nombre, o.fecha_subida, o.ancho_px, o.alto_px,
           o.minzoom, o.maxzoom, o.ruta_archivo,
           ST_XMin(o.bounds) AS oeste, ST_YMin(o.bounds) AS sur,
           ST_XMax(o.bounds) AS este, ST_YMax(o.bounds) AS norte,
           u.nombre_completo AS usuario_nombre
    FROM ortomosaicos o
    LEFT JOIN usuarios u ON u.id = o.usuario_id
"""


def _fila_a_meta(fila: Dict) -> Dict:
    return {
        "id": fila["id"],
        "nombre": fila["nombre"],
        "usuario_nombre": fila["usuario_nombre"],
        "fecha_subida": fila["fecha_subida"].isoformat(),
        "ancho_px": fila["ancho_px"],
        "alto_px": fila["alto_px"],
        "bounds": [[fila["sur"], fila["oeste"]], [fila["norte"], fila["este"]]],
        "minzoom": fila["minzoom"],
        "maxzoom": fila["maxzoom"],
    }


def registrar_ortomosaico(
    id_: str, usuario_id: int, nombre: str, ancho_px: int, alto_px: int,
    bounds, minzoom: int, maxzoom: int, ruta_archivo: str
) -> Dict:
    (sur, oeste), (norte, este) = bounds
    with conexion() as con:
        con.execute(
            """
            INSERT INTO ortomosaicos
                (id, usuario_id, nombre, ancho_px, alto_px, bounds, minzoom, maxzoom, ruta_archivo)
            VALUES (%s, %s, %s, %s, %s, ST_MakeEnvelope(%s, %s, %s, %s, 4326), %s, %s, %s)
            """,
            (id_, usuario_id, nombre, ancho_px, alto_px, oeste, sur, este, norte, minzoom, maxzoom, ruta_archivo),
        )
        con.commit()
    return obtener_ortomosaico(id_)


def listar_ortomosaicos() -> List[Dict]:
    with conexion() as con:
        filas = con.execute(_SELECT_ORTOMOSAICO + " ORDER BY o.fecha_subida DESC").fetchall()
        return [_fila_a_meta(f) for f in filas]


def obtener_ortomosaico(id_: str) -> Optional[Dict]:
    with conexion() as con:
        fila = con.execute(_SELECT_ORTOMOSAICO + " WHERE o.id = %s", (id_,)).fetchone()
        return _fila_a_meta(fila) if fila else None


def obtener_ruta_archivo(id_: str) -> Optional[str]:
    """Para el dependency de FastAPI que resuelve la carpeta en disco — no trae todo el resto."""
    with conexion() as con:
        fila = con.execute("SELECT ruta_archivo FROM ortomosaicos WHERE id = %s", (id_,)).fetchone()
        return fila["ruta_archivo"] if fila else None


# ==========================================================
# Análisis
# ==========================================================
def crear_analisis(
    ortomosaico_id: str, usuario_id: int, version_modelo: str,
    conf_umbral: float, cuadrante: Optional[int], total_celdas: int,
    escala: int = 1
) -> int:
    with conexion() as con:
        fila = con.execute(
            """
            INSERT INTO analisis
                (ortomosaico_id, usuario_id, version_modelo, conf_umbral, cuadrante,
                 total_celdas, escala, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'en_progreso')
            RETURNING id
            """,
            (ortomosaico_id, usuario_id, version_modelo, conf_umbral, cuadrante,
             total_celdas, escala),
        ).fetchone()
        con.commit()
        return fila["id"]


def finalizar_analisis(analisis_id: int, celdas_activas: int, estado: str) -> None:
    with conexion() as con:
        con.execute(
            "UPDATE analisis SET fecha_fin = now(), celdas_activas = %s, estado = %s WHERE id = %s",
            (celdas_activas, estado, analisis_id),
        )
        con.commit()


def obtener_analisis(analisis_id: int) -> Optional[Dict]:
    with conexion() as con:
        fila = con.execute(
            """
            SELECT a.id, a.ortomosaico_id, a.version_modelo, a.conf_umbral, a.cuadrante,
                   a.escala, a.fecha_inicio, a.fecha_fin, a.total_celdas, a.celdas_activas,
                   a.estado, u.nombre_completo AS usuario_nombre
            FROM analisis a
            LEFT JOIN usuarios u ON u.id = a.usuario_id
            WHERE a.id = %s
            """,
            (analisis_id,),
        ).fetchone()
        return dict(fila) if fila else None


def listar_analisis(ortomosaico_id: str) -> List[Dict]:
    """Historial de corridas de una imagen, más reciente primero."""
    with conexion() as con:
        filas = con.execute(
            """
            SELECT a.id, a.version_modelo, a.conf_umbral, a.cuadrante,
                   a.escala, a.fecha_inicio, a.fecha_fin, a.total_celdas, a.celdas_activas,
                   a.estado, u.nombre_completo AS usuario_nombre,
                   COUNT(d.id) AS total_detecciones
            FROM analisis a
            LEFT JOIN usuarios u ON u.id = a.usuario_id
            LEFT JOIN detecciones d ON d.analisis_id = a.id
            WHERE a.ortomosaico_id = %s
            GROUP BY a.id, u.nombre_completo
            ORDER BY a.fecha_inicio DESC
            """,
            (ortomosaico_id,),
        ).fetchall()
        return [
            {
                "id": f["id"],
                "version_modelo": f["version_modelo"],
                "conf_umbral": f["conf_umbral"],
                "cuadrante": f["cuadrante"],
                "escala": f["escala"],
                "fecha_inicio": f["fecha_inicio"].isoformat(),
                "fecha_fin": f["fecha_fin"].isoformat() if f["fecha_fin"] else None,
                "total_celdas": f["total_celdas"],
                "celdas_activas": f["celdas_activas"],
                "estado": f["estado"],
                "usuario_nombre": f["usuario_nombre"],
                "total_detecciones": f["total_detecciones"],
            }
            for f in filas
        ]


# ==========================================================
# Detecciones
# ==========================================================
def _contorno_geojson(deteccion: Dict) -> Optional[str]:
    """
    El contorno de una detección como GeoJSON para pasárselo a PostGIS, o None si
    el análisis corrió con un modelo de detección (no hay contorno).

    georref lo entrega como [[lat, lon], ...] porque así lo dibuja Leaflet;
    GeoJSON y PostGIS van al revés, lon primero. El anillo se cierra acá: un
    polígono de GeoJSON repite el primer vértice al final y los contornos que
    devuelve ia-inferencia no lo traen.
    """
    contorno = deteccion.get("contorno")
    if not contorno or len(contorno) < 3:
        return None
    anillo = [[lon, lat] for lat, lon in contorno]
    if anillo[0] != anillo[-1]:
        anillo.append(anillo[0])
    return json.dumps({"type": "Polygon", "coordinates": [anillo]})


def _contorno_plano(deteccion: Dict) -> Optional[List[int]]:
    """El contorno en píxeles como array plano para contorno_global_px."""
    contorno = deteccion.get("contorno_global_px")
    if not contorno:
        return None
    return [round(v) for punto in contorno for v in punto]


def insertar_detecciones(analisis_id: int, detecciones: List[Dict]) -> None:
    """Bulk insert de un bloque del streaming. detecciones viene en el
    formato de georref.traducir_deteccion (gps_centro, box_global_px, etc)."""
    if not detecciones:
        return
    filas = [
        (
            analisis_id,
            d["clase"],
            d["confianza"],
            d["gps_centro"]["lon"],
            d["gps_centro"]["lat"],
            d["box_global_px"],
            d["fila"],
            d["col"],
            _contorno_geojson(d),
            _contorno_plano(d),
        )
        for d in detecciones
    ]
    with conexion() as con:
        # El contorno de una máscara puede salir con el borde cruzado, y un
        # polígono así no es válido en PostGIS: ST_MakeValid lo arregla, pero
        # parte el anillo en varios, de ahí el MULTIPOLYGON de la columna.
        # CollectionExtract(…, 3) se queda solo con las partes con superficie
        # (MakeValid puede devolver también los bordes como líneas). Si el
        # GeoJSON es NULL toda la expresión da NULL, que es lo que queremos para
        # un análisis sin contornos.
        con.cursor().executemany(
            """
            INSERT INTO detecciones
                (analisis_id, clase, confianza, ubicacion, box_global_px, fila, col,
                 contorno, contorno_global_px)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s,
                    ST_Multi(ST_CollectionExtract(
                        ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 3)),
                    %s)
            """,
            filas,
        )
        con.commit()


# Dos mitades de una mancha cortada por el borde de una celda quedan pegadas,
# pero no exactamente: el contorno se simplifica en ia-inferencia (Douglas-Peucker
# al 0,4 % del perímetro) y eso corre el borde de cada mitad uno o dos píxeles.
# 25 cm son unos 8 píxeles a 3,3 cm/px: alcanza para esa holgura y queda muy por
# debajo de la separación entre dos manchas que de verdad son distintas.
TOLERANCIA_FUSION_M = 0.25


def _raiz(padres: Dict[int, int], x: int) -> int:
    while padres[x] != x:
        padres[x] = padres[padres[x]]
        x = padres[x]
    return x


def fusionar_detecciones_vecinas(
    analisis_id: int,
    a_pixeles: Callable[[List[Tuple[float, float]]], List[Tuple[float, float]]],
    tolerancia_m: float = TOLERANCIA_FUSION_M,
) -> Dict:
    """
    Une las detecciones de la misma clase que quedaron partidas por el borde de
    una celda, y devuelve cuántas se fusionaron.

    El recorrido parte el campo en una grilla, así que una mancha más ancha que
    una celda sale como dos detecciones, cada una con su superficie: el informe
    cuenta dos manchas donde hay una y ninguna de las dos mide lo que mide la
    mancha. Esto lo arregla después de analizar, que es el único momento en el
    que están todas las piezas: dos mitades pueden haber caído en bloques
    distintos del streaming.

    **Solo se fusionan detecciones de celdas distintas**, y eso no es un detalle.
    Medido sobre un análisis real de 463 detecciones, de los pares de la misma
    clase que se tocan 284 caen dentro de una misma celda y 54 cruzan el borde.
    Los primeros son manchas que el modelo decidió separar aunque se toquen, y
    unirlas sería pisarle la decisión; el artefacto que hay que corregir es el
    segundo, que lo introdujo la grilla y no el modelo.

    No hace falta solapar la grilla para esto: las dos mitades quedan a
    distancia ~0 porque las dos se cortaron contra la misma línea.

    Se corre **una sola vez por análisis**, desde el generador de analisis.py.
    No es idempotente: la detección que sale de fusionar un grupo se queda con
    la celda de su pieza mayor, así que ya no está contenida en esa celda y en
    una segunda pasada podría unirse con vecinas que la primera no tocó.

    `a_pixeles` convierte [(lat, lon), ...] a píxeles del ortomosaico. Se recibe
    de afuera para que este módulo no tenga que abrir el raster, y hace falta
    porque la detección fusionada también necesita su contorno en píxeles: es
    con lo que el informe en PDF dibuja sobre la imagen.
    """
    resumen = {"grupos": 0, "fusionadas": 0}

    with conexion() as con:
        aristas = con.execute(
            """
            SELECT a.id AS a_id, b.id AS b_id
            FROM detecciones a
            JOIN detecciones b
              ON b.analisis_id = a.analisis_id
             AND b.id > a.id
             AND b.clase = a.clase
             -- Celdas distintas: ver el docstring, es la condición que distingue
             -- el corte de la grilla de dos manchas vecinas de verdad
             AND (b.fila, b.col) <> (a.fila, a.col)
             -- Y celdas vecinas. No es una aproximación: un contorno no se sale
             -- de su celda, así que dos piezas a menos de la tolerancia están sí
             -- o sí en celdas que se tocan; dos celdas que no se tocan están a
             -- un ancho de celda de distancia (640 px, unos 21 m). Va acá y no
             -- en el filtro de después porque es lo único que puede usar un
             -- índice: ST_DWithin sobre geography no usa el GIST de contorno,
             -- y sin esta línea la consulta compara cada detección contra todas
             -- (medido: 195 s contra 4,2 s en un análisis de 2366 detecciones).
             AND ABS(b.fila - a.fila) <= 1 AND ABS(b.col - a.col) <= 1
             AND ST_DWithin(a.contorno::geography, b.contorno::geography, %s)
            WHERE a.analisis_id = %s
              AND a.contorno IS NOT NULL
              AND b.contorno IS NOT NULL
            """,
            (tolerancia_m, analisis_id),
        ).fetchall()

    if not aristas:
        return resumen

    padres: Dict[int, int] = {}
    for arista in aristas:
        for ident in (arista["a_id"], arista["b_id"]):
            padres.setdefault(ident, ident)
        ra, rb = _raiz(padres, arista["a_id"]), _raiz(padres, arista["b_id"])
        if ra != rb:
            padres[rb] = ra

    grupos: Dict[int, List[int]] = {}
    for ident in padres:
        grupos.setdefault(_raiz(padres, ident), []).append(ident)

    # Una sola conexión para todos los grupos: un análisis denso puede dejar
    # cientos, y abrir una por grupo multiplica el costo por nada.
    with conexion() as con:
        for ids in grupos.values():
            if len(ids) < 2:
                continue
            fila = con.execute(
                """
                SELECT clase,
                       MAX(confianza) AS confianza,
                       ST_X(ST_Centroid(ST_Union(contorno))) AS lon,
                       ST_Y(ST_Centroid(ST_Union(contorno))) AS lat,
                       ST_AsGeoJSON(ST_Multi(ST_CollectionExtract(
                           ST_MakeValid(ST_Union(contorno)), 3))) AS geojson,
                       -- La celda de la pieza más grande: es la que mejor
                       -- representa dónde está la mancha dentro de la grilla
                       (array_agg(fila ORDER BY ST_Area(contorno::geography) DESC))[1] AS fila,
                       (array_agg(col  ORDER BY ST_Area(contorno::geography) DESC))[1] AS col,
                       MIN(box_global_px[1]) AS x1, MIN(box_global_px[2]) AS y1,
                       MAX(box_global_px[3]) AS x2, MAX(box_global_px[4]) AS y2
                FROM detecciones
                WHERE id = ANY(%s)
                GROUP BY clase
                """,
                (ids,),
            ).fetchone()
            if fila is None or not fila["geojson"]:
                continue

            # El anillo de la pieza de mayor área, igual que al leer una
            # detección: las otras piezas son esquirlas de unos pocos píxeles
            piezas = json.loads(fila["geojson"])["coordinates"]
            anillo = max(piezas, key=lambda p: len(p[0]))[0]
            pixeles = a_pixeles([(lat, lon) for lon, lat in anillo])
            plano = [int(round(v)) for punto in pixeles for v in punto]

            con.execute(
                """
                INSERT INTO detecciones
                    (analisis_id, clase, confianza, ubicacion, box_global_px, fila, col,
                     contorno, contorno_global_px)
                VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s,
                        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s)
                """,
                (
                    analisis_id, fila["clase"], fila["confianza"], fila["lon"], fila["lat"],
                    [fila["x1"], fila["y1"], fila["x2"], fila["y2"]],
                    fila["fila"], fila["col"], fila["geojson"], plano,
                ),
            )
            con.execute("DELETE FROM detecciones WHERE id = ANY(%s)", (ids,))

            resumen["grupos"] += 1
            resumen["fusionadas"] += len(ids)

        # Un solo commit: o se fusiona todo o no se fusiona nada. A mitad de
        # camino el análisis quedaría con unas manchas unidas y otras no, que es
        # peor que no haber fusionado, porque no se nota.
        con.commit()

    return resumen


def obtener_detecciones(analisis_id: int) -> List[Dict]:
    """
    Para volver a ver un análisis pasado sin tener que re-ejecutarlo. Devuelve lo
    mismo que georref.traducir_deteccion, así el front no distingue un análisis
    en vivo de uno guardado.

    El contorno vuelve a salir como [[lat, lon], ...] (orden de Leaflet) y, si el
    multipolígono quedó partido en varias piezas, se devuelve la más grande: el
    anillo principal es la mancha y los restos son esquirlas de unos píxeles.
    La superficie, en cambio, se mide sobre todas las piezas.
    """
    with conexion() as con:
        filas = con.execute(
            """
            SELECT clase, confianza, box_global_px, fila, col,
                   ST_Y(ubicacion) AS lat, ST_X(ubicacion) AS lon,
                   contorno_global_px,
                   ST_AsGeoJSON(
                       (SELECT geom FROM ST_Dump(contorno)
                        ORDER BY ST_Area(geom) DESC LIMIT 1)
                   ) AS contorno_json,
                   -- Proyectado a geography para que el área salga en metros y
                   -- no en grados cuadrados, que no significan nada
                   ST_Area(contorno::geography) AS area_m2
            FROM detecciones WHERE analisis_id = %s ORDER BY id
            """,
            (analisis_id,),
        ).fetchall()

    detecciones = []
    for f in filas:
        deteccion = {
            "fila": f["fila"],
            "col": f["col"],
            "clase": f["clase"],
            "confianza": f["confianza"],
            "box_global_px": f["box_global_px"],
            "gps_centro": {"lat": f["lat"], "lon": f["lon"]},
        }
        if f["contorno_json"]:
            anillo = json.loads(f["contorno_json"])["coordinates"][0]
            deteccion["contorno"] = [[lat, lon] for lon, lat in anillo]
            deteccion["area_m2"] = round(float(f["area_m2"]), 2)
        if f["contorno_global_px"]:
            plano = f["contorno_global_px"]
            deteccion["contorno_global_px"] = [
                [plano[i], plano[i + 1]] for i in range(0, len(plano) - 1, 2)
            ]
        detecciones.append(deteccion)
    return detecciones


def exportar_geojson(analisis_id: int) -> Dict:
    """
    PostGIS arma el FeatureCollection directo, no hay que escribirlo a mano.

    La geometría de cada detección es su contorno cuando lo tiene y el punto
    cuando no (análisis con un modelo de detección). Esa es la diferencia que se
    nota al abrir el archivo en QGIS: polígonos que se pueden medir y recortar
    contra el lote, en vez de un montón de puntos.
    """
    with conexion() as con:
        fila = con.execute(
            """
            SELECT jsonb_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(jsonb_agg(
                    jsonb_build_object(
                        'type', 'Feature',
                        'geometry', COALESCE(ST_AsGeoJSON(contorno)::jsonb, ST_AsGeoJSON(ubicacion)::jsonb),
                        'properties', jsonb_build_object(
                            'clase', clase, 'confianza', confianza, 'fila', fila, 'col', col,
                            'area_m2', ROUND(ST_Area(contorno::geography)::numeric, 2),
                            -- El centro sigue estando aunque la geometría sea el
                            -- contorno: es con lo que se ubica en el campo
                            'lat', ST_Y(ubicacion), 'lon', ST_X(ubicacion)
                        )
                    )
                ), '[]'::jsonb)
            ) AS geojson
            FROM detecciones WHERE analisis_id = %s
            """,
            (analisis_id,),
        ).fetchone()
        return fila["geojson"]


def exportar_csv(analisis_id: int) -> str:
    detecciones = obtener_detecciones(analisis_id)
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    # area_m2 queda vacía en los análisis sin contorno
    escritor.writerow(["clase", "confianza", "lat", "lon", "area_m2", "fila", "col"])
    for d in detecciones:
        escritor.writerow([
            d["clase"], d["confianza"], d["gps_centro"]["lat"], d["gps_centro"]["lon"],
            d.get("area_m2", ""), d["fila"], d["col"],
        ])
    return buffer.getvalue()


# ==========================================================
# Dashboard — los KPI reales (reemplaza las métricas hardcodeadas del front)
# ==========================================================
def estadisticas_dashboard() -> Dict:
    with conexion() as con:
        totales = con.execute(
            """
            SELECT (SELECT COUNT(*) FROM ortomosaicos) AS total_ortomosaicos,
                   (SELECT COUNT(*) FROM analisis) AS total_analisis,
                   (SELECT MAX(fecha_inicio) FROM analisis) AS ultima_actualizacion
            """
        ).fetchone()

        por_clase = con.execute(
            """
            WITH ultimo AS (
                SELECT DISTINCT ON (ortomosaico_id) id, celdas_activas
                FROM analisis
                WHERE estado = 'completo'
                ORDER BY ortomosaico_id, fecha_inicio DESC
            )
            SELECT d.clase, COUNT(*) AS cantidad, COUNT(DISTINCT (d.fila, d.col)) AS celdas,
                   (SELECT COALESCE(SUM(celdas_activas), 0) FROM ultimo) AS total_celdas_activas
            FROM detecciones d
            JOIN ultimo u ON u.id = d.analisis_id
            GROUP BY d.clase
            ORDER BY cantidad DESC
            """
        ).fetchall()

        por_version = con.execute(
            """
            SELECT a.version_modelo, AVG(d.confianza) AS confianza_promedio,
                   COUNT(DISTINCT a.id) AS corridas, COUNT(d.id) AS detecciones
            FROM analisis a
            JOIN detecciones d ON d.analisis_id = a.id
            GROUP BY a.version_modelo
            ORDER BY MAX(a.fecha_inicio) DESC
            """
        ).fetchall()

        eficiencia = con.execute(
            """
            SELECT fecha_inicio, total_celdas,
                   EXTRACT(EPOCH FROM (fecha_fin - fecha_inicio)) AS duracion_seg
            FROM analisis
            WHERE estado = 'completo' AND fecha_fin IS NOT NULL AND total_celdas > 0
            ORDER BY fecha_inicio DESC
            LIMIT 10
            """
        ).fetchall()

    total_celdas_activas = por_clase[0]["total_celdas_activas"] if por_clase else 0
    maleza = next((f for f in por_clase if f["clase"] == "maleza"), None)
    pct_cobertura = (
        round(100 * maleza["celdas"] / total_celdas_activas, 1)
        if maleza and total_celdas_activas > 0
        else 0.0
    )

    historial_eficiencia = [
        {
            "fecha": f["fecha_inicio"].isoformat(),
            "seg_por_celda": round(f["duracion_seg"] / f["total_celdas"], 3),
        }
        for f in reversed(eficiencia)
    ]
    promedio_seg_por_celda = (
        round(sum(h["seg_por_celda"] for h in historial_eficiencia) / len(historial_eficiencia), 3)
        if historial_eficiencia
        else None
    )

    return {
        "total_ortomosaicos": totales["total_ortomosaicos"],
        "total_analisis": totales["total_analisis"],
        "ultima_actualizacion": totales["ultima_actualizacion"].isoformat() if totales["ultima_actualizacion"] else None,
        "cobertura": {
            "clase_principal": por_clase[0]["clase"] if por_clase else None,
            "pct_cobertura": pct_cobertura,
            "detecciones_totales": sum(f["cantidad"] for f in por_clase),
        },
        "detecciones_por_clase": [{"clase": f["clase"], "cantidad": f["cantidad"]} for f in por_clase],
        "modelo": {
            "por_version": [
                {
                    "version_modelo": f["version_modelo"],
                    "confianza_promedio": round(float(f["confianza_promedio"]), 3),
                    "corridas": f["corridas"],
                    "detecciones": f["detecciones"],
                }
                for f in por_version
            ]
        },
        "eficiencia": {
            "promedio_seg_por_celda": promedio_seg_por_celda,
            "historial": historial_eficiencia,
        },
    }
