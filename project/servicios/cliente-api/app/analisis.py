import math
import os
from typing import Generator, Optional
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
    escala: int = 1
) -> Generator[dict, None, None]:
    """
    Generador que procesa el ortomosaico en bloques de a lo sumo TAMANO_LOTE_MAX celdas.
    Lee ventanas del raster mediante py-geo, envía teselas activas al servicio
    ia-inferencia mediante HTTP, traduce las cajas a coordenadas globales y WGS84,
    y las persiste en la tabla detecciones a medida que llegan (no se acumulan
    en memoria ni se pisan corridas anteriores: cada llamada crea su propia
    fila en "analisis").

    `escala` es cuánto se aleja la cámara: con 1 cada celda son `imgsz` píxeles
    del raster leídos tal cual, y con 4 son `imgsz * 4` reducidos a `imgsz`, o
    sea el mismo encuadre con cuatro veces más campo. Hace falta porque una
    mancha más grande que la celda nunca entra entera en la imagen y el modelo
    la corta; ver GeoHandler. Una pasada gruesa recorre 16 veces menos celdas,
    así que es más barata que una fina, no más cara.
    """
    cliente_ia = ClienteIA()
    info_modelo = cliente_ia.obtener_modelo()
    tamano_tile = info_modelo.get("imgsz", 640)
    version_modelo = info_modelo.get("version", "v1")

    geo = GeoHandler(ruta_tif, tamano_tile=tamano_tile, escala=escala)
    celdas = geo.obtener_lista_cuadrantes(cuadrante=cuadrante)
    total_celdas = len(celdas)

    analisis_id = datos.crear_analisis(
        ortomosaico_id=ortomosaico_id,
        usuario_id=usuario_id,
        version_modelo=version_modelo,
        conf_umbral=conf,
        cuadrante=cuadrante,
        total_celdas=total_celdas,
        escala=geo.escala,
    )

    tamano_segmento = min(TAMANO_LOTE_MAX, max(1, math.ceil(total_celdas / 10)))
    segmentos = [celdas[i:i + tamano_segmento] for i in range(0, total_celdas, tamano_segmento)]

    total_acumuladas = 0
    total_activas = 0
    estado_final = "completo"

    print(f"[INICIO] analisis={analisis_id} {total_celdas} celdas en {len(segmentos)} bloques (max {tamano_segmento} celdas c/u). imgsz={tamano_tile} escala={geo.escala} celda={geo.tamano_celda}px")

    try:
        for seg_idx, segmento in enumerate(segmentos):
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
                        detecciones_bloque.append(det_global)

            if detecciones_bloque:
                datos.insertar_detecciones(analisis_id, detecciones_bloque)
            total_acumuladas += len(detecciones_bloque)

            progreso_pct = round(((seg_idx + 1) / len(segmentos)) * 100, 1) if segmentos else 100.0

            chunk = {
                "analisis_id": analisis_id,
                "escala": geo.escala,
                "bloque": seg_idx + 1,
                "total_bloques": len(segmentos),
                "progreso_pct": progreso_pct,
                "activas": len(lote_a_enviar),
                "detecciones": detecciones_bloque,
                "total_acumuladas": total_acumuladas
            }
            yield chunk

        # Recién acá están todas las piezas: una mancha partida por el borde de
        # una celda pudo salir en dos bloques distintos del streaming, así que
        # esto no se puede hacer mientras se recorre. Ver
        # datos.fusionar_detecciones_vecinas sobre por qué solo entre celdas.
        fusion = datos.fusionar_detecciones_vecinas(
            analisis_id, geo.latlon_a_pixeles_globales
        )
        # Y después de unir las piezas, sacar las repetidas: YOLO hace NMS sobre
        # las cajas y no sobre las máscaras, así que la misma mancha puede quedar
        # detectada dos veces, una adentro de la otra. No se nota en el mapa pero
        # sí al sumar superficies, que es lo que hacen el informe y el dashboard.
        # Va después de la fusión porque una mancha recién armada de dos mitades
        # puede contener detecciones que antes no contenía.
        supresion = datos.suprimir_detecciones_anidadas(analisis_id)
        fusion["suprimidas"] = supresion["suprimidas"]

        if fusion["grupos"]:
            # Cada grupo deja una detección donde había varias
            total_acumuladas -= fusion["fusionadas"] - fusion["grupos"]
            print(
                f"[FUSION] analisis={analisis_id}: {fusion['fusionadas']} detecciones "
                f"partidas por el borde de una celda quedaron en {fusion['grupos']}"
            )
        if supresion["suprimidas"]:
            total_acumuladas -= supresion["suprimidas"]
            print(
                f"[DUPLICADAS] analisis={analisis_id}: {supresion['suprimidas']} detecciones "
                f"contenidas en otra de la misma clase"
            )

        if fusion["grupos"] or supresion["suprimidas"]:
            # El navegador ya recibió las piezas sueltas por SSE; este chunk le
            # avisa que lo guardado cambió y con cuánto, para que las recargue.
            yield {
                "analisis_id": analisis_id,
                "escala": geo.escala,
                "bloque": len(segmentos),
                "total_bloques": len(segmentos),
                "progreso_pct": 100.0,
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
        geo.cerrar()
        datos.finalizar_analisis(analisis_id, celdas_activas=total_activas, estado=estado_final)
        print(f"[GUARDADO] analisis={analisis_id} ({total_acumuladas} detecciones, estado={estado_final})")
