import math
import os
from typing import Generator, List, Optional
import cv2

try:
    from py_geo.geo import GeoHandler
except ImportError:
    import sys
    from pathlib import Path
    ruta_compartido = Path(__file__).resolve().parent.parent.parent.parent / "compartido" / "py-geo"
    if str(ruta_compartido) not in sys.path:
        sys.path.insert(0, str(ruta_compartido))
    from py_geo.geo import GeoHandler

import datos
from cliente_ia import ClienteIA
from georref import traducir_deteccion

TAMANO_LOTE_MAX = int(os.environ.get("TAMANO_LOTE_MAX", "16"))


def ejecutar_inspeccion_segmentada(
    ruta_tif: str,
    ortomosaico_id: str,
    usuario_id: int,
    cuadrante: Optional[int] = None,
    conf: float = 0.10,
    escalas: Optional[List[int]] = None
) -> Generator[dict, None, None]:
    """
    Generador que recorre el ortomosaico y persiste lo que encuentra.

    Lee ventanas del raster mediante py-geo, envía teselas activas a
    ia-inferencia por HTTP, traduce lo que vuelve a coordenadas globales y WGS84
    y lo guarda a medida que llega (no se acumula en memoria ni se pisan
    corridas anteriores: cada llamada crea su propia fila en "analisis").

    `escalas` son las pasadas, en orden. Una pasada de escala 1 lee celdas de
    `imgsz` píxeles del raster tal cual; una de escala 4 lee celdas de
    `imgsz * 4` reducidas a `imgsz`, o sea el mismo encuadre con 16 veces más
    campo. Con `[4, 1]` la cámara primero se aleja —y ahí entran enteras las
    manchas que a resolución nativa no caben en una celda, que son las que el
    modelo venía cortando— y después se acerca, para las chicas y las escondidas
    entre la caña. La pasada gruesa recorre 16 veces menos celdas, así que
    sumarla cuesta poco: medido sobre El Azul, un cuadrante entero a escala 4
    son 6 s contra 54 s a escala 1.

    El post-proceso (unir piezas partidas por un borde, sacar duplicadas) corre
    **por pasada**, no sobre la mezcla: ver datos.suprimir_detecciones_anidadas
    sobre por qué entre escalas distintas la contención no es un duplicado.
    """
    escalas = [int(e) for e in (escalas or [1])] or [1]
    cliente_ia = ClienteIA()
    info_modelo = cliente_ia.obtener_modelo()
    tamano_tile = info_modelo.get("imgsz", 640)
    version_modelo = info_modelo.get("version", "v1")

    # Se arman todas las pasadas antes de empezar para saber cuántas celdas hay
    # en total, que es contra lo que se mide el progreso de punta a punta.
    pasadas = []
    for escala in escalas:
        geo = GeoHandler(ruta_tif, tamano_tile=tamano_tile, escala=escala)
        celdas = geo.obtener_lista_cuadrantes(cuadrante=cuadrante)
        tamano_segmento = min(TAMANO_LOTE_MAX, max(1, math.ceil(len(celdas) / 10)))
        segmentos = [celdas[i:i + tamano_segmento] for i in range(0, len(celdas), tamano_segmento)]
        pasadas.append({"geo": geo, "segmentos": segmentos, "celdas": len(celdas)})

    total_celdas = sum(p["celdas"] for p in pasadas)
    total_bloques = sum(len(p["segmentos"]) for p in pasadas)

    analisis_id = datos.crear_analisis(
        ortomosaico_id=ortomosaico_id,
        usuario_id=usuario_id,
        version_modelo=version_modelo,
        conf_umbral=conf,
        cuadrante=cuadrante,
        total_celdas=total_celdas,
        escalas=[p["geo"].escala for p in pasadas],
    )

    total_acumuladas = 0
    total_activas = 0
    estado_final = "completo"
    bloque_global = 0

    detalle = ", ".join(
        f"escala {p['geo'].escala}: {p['celdas']} celdas de {p['geo'].tamano_celda}px" for p in pasadas
    )
    print(f"[INICIO] analisis={analisis_id} {total_celdas} celdas en {total_bloques} bloques. imgsz={tamano_tile} ({detalle})")

    try:
        for pasada in pasadas:
            geo = pasada["geo"]
            for segmento in pasada["segmentos"]:
                celdas_por_id = {}
                lote_a_enviar = []

                for celda in segmento:
                    tile = geo.leer_tile_filtrado(celda["x"], celda["y"], celda["ancho"], celda["alto"])
                    if tile is not None:
                        # id opaco único para correlacionar la respuesta
                        tile_id = f"c_{celda['fila']}_{celda['col']}_{celda['x']}_{celda['y']}"
                        celdas_por_id[tile_id] = celda

                        ok, buf = cv2.imencode(".jpg", tile, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        if ok:
                            lote_a_enviar.append((tile_id, buf.tobytes()))

                total_activas += len(lote_a_enviar)

                detecciones_bloque = []
                if lote_a_enviar:
                    detecciones_ia = cliente_ia.detectar_lote(lote_a_enviar, conf=conf)
                    for det in detecciones_ia:
                        tile_id = det["id"]
                        if tile_id in celdas_por_id:
                            celda_meta = celdas_por_id[tile_id]
                            det_global = traducir_deteccion(det, celda_meta, geo)
                            det_global["escala"] = geo.escala
                            detecciones_bloque.append(det_global)

                if detecciones_bloque:
                    datos.insertar_detecciones(analisis_id, detecciones_bloque, escala=geo.escala)
                total_acumuladas += len(detecciones_bloque)
                bloque_global += 1

                yield {
                    "analisis_id": analisis_id,
                    "escala": geo.escala,
                    "bloque": bloque_global,
                    "total_bloques": total_bloques,
                    "progreso_pct": round((bloque_global / total_bloques) * 100, 1) if total_bloques else 100.0,
                    "activas": len(lote_a_enviar),
                    "detecciones": detecciones_bloque,
                    "total_acumuladas": total_acumuladas
                }

            # Al cerrar la pasada están todas sus piezas: una mancha partida por
            # el borde de una celda pudo salir en dos bloques distintos del
            # streaming, así que esto no se puede hacer mientras se recorre.
            fusion = datos.fusionar_detecciones_vecinas(
                analisis_id, geo.latlon_a_pixeles_globales, escala=geo.escala
            )
            # Y después de unir las piezas, sacar las repetidas: YOLO hace NMS
            # sobre las cajas y no sobre las máscaras, así que la misma mancha
            # puede quedar detectada dos veces, una adentro de la otra. No se
            # nota en el mapa pero sí al sumar superficies. Va después de la
            # fusión porque una mancha recién armada de dos mitades puede
            # contener detecciones que antes no contenía.
            supresion = datos.suprimir_detecciones_anidadas(analisis_id, escala=geo.escala)
            fusion["suprimidas"] = supresion["suprimidas"]
            fusion["escala"] = geo.escala

            if fusion["grupos"]:
                # Cada grupo deja una detección donde había varias
                total_acumuladas -= fusion["fusionadas"] - fusion["grupos"]
                print(
                    f"[FUSION] analisis={analisis_id} escala={geo.escala}: {fusion['fusionadas']} "
                    f"detecciones partidas por el borde de una celda quedaron en {fusion['grupos']}"
                )
            if supresion["suprimidas"]:
                total_acumuladas -= supresion["suprimidas"]
                print(
                    f"[DUPLICADAS] analisis={analisis_id} escala={geo.escala}: "
                    f"{supresion['suprimidas']} detecciones contenidas en otra de la misma clase"
                )

            if fusion["grupos"] or supresion["suprimidas"]:
                # El navegador ya recibió las piezas sueltas por SSE; este chunk
                # le avisa que lo guardado cambió, para que las recargue.
                yield {
                    "analisis_id": analisis_id,
                    "escala": geo.escala,
                    "bloque": bloque_global,
                    "total_bloques": total_bloques,
                    "progreso_pct": round((bloque_global / total_bloques) * 100, 1) if total_bloques else 100.0,
                    "activas": 0,
                    "detecciones": [],
                    "total_acumuladas": total_acumuladas,
                    "fusion": fusion,
                }

    except KeyboardInterrupt:
        print("\n[AVISO] Inspección detenida manualmente.")
        estado_final = "error"

    except Exception as e:
        print(f"[ERROR] analisis={analisis_id}: {e}")
        estado_final = "error"
        raise

    finally:
        for pasada in pasadas:
            pasada["geo"].cerrar()
        datos.finalizar_analisis(analisis_id, celdas_activas=total_activas, estado=estado_final)
        print(f"[GUARDADO] analisis={analisis_id} ({total_acumuladas} detecciones, estado={estado_final})")
