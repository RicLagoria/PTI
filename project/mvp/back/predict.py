import json
import math
import os
from geo import GeoHandler
from detector import FieldDetector

# Techo de celdas que se mandan juntas a YOLO en una sola llamada a predict().
# Antes el lote se armaba como total_celdas/10, así que en un ortomosaico
# grande (miles de celdas) cada lote terminaba siendo de cientos de tiles de
# una sola vez: arma un tensor gigante y revienta la memoria (visto en la
# práctica: mató el proceso por OOM con una imagen de ~2400 celdas). Con un
# tope fijo, el consumo de RAM por lote queda acotado sin importar cuán
# grande sea la imagen.
#
# Ojo, esto NO es "más grande = más rápido": medido en CPU (sin GPU, 4
# núcleos/8 hilos) sobre el mismo cuadrante de prueba (579 celdas), el
# tiempo total por tamaño de lote fue:
#   32 -> 143.0s   16 -> 107.6s   8 -> 92.6s   4 -> 81.7s (mejor)   1 -> 99.9s
# Hay un óptimo en el medio (acá dio 4): lotes grandes sufren más overhead
# de armar/mover el tensor en CPU, y lotes de a 1 pierden el paralelismo
# vectorizado del batching. Conviene medir de nuevo si cambia el hardware
# (en un server con GPU probablemente el óptimo esté mucho más arriba).
TAMANO_LOTE_MAX = int(os.environ.get("TAMANO_LOTE_MAX", "16"))

def ejecutar_inspeccion_segmentada(ruta_tif, cuadrante=3, ruta_json="detecciones_campo.json", conf=0.10):
    """
    Generador que procesa el ortomosaico en bloques de a lo sumo
    TAMANO_LOTE_MAX celdas. En cada iteración emite (yield) un diccionario
    con el progreso y las nuevas detecciones del bloque para que la API las
    envíe al front.
    """
    geo = GeoHandler(ruta_tif, tamano_tile=640)
    detector = FieldDetector(conf_threshold=conf)

    celdas = geo.obtener_lista_cuadrantes(cuadrante=cuadrante)
    total_celdas = len(celdas)

    tamano_segmento = min(TAMANO_LOTE_MAX, max(1, math.ceil(total_celdas / 10)))
    segmentos = [celdas[i:i + tamano_segmento] for i in range(0, total_celdas, tamano_segmento)]

    estructura_datos = {
        "metadata": {
            "archivo": ruta_tif,
            "ancho_total_px": geo.ancho_total,
            "alto_total_px": geo.alto_total,
            "tamano_tile": geo.tamano_tile,
            "total_celdas": total_celdas,
            "segmentos_totales": len(segmentos)
        },
        "progreso_actual_pct": 0,
        "bloques_procesados": 0,
        "detecciones": []
    }

    print(f"[INICIO] {total_celdas} celdas divididas en {len(segmentos)} bloques de hasta {tamano_segmento} celdas c/u.")

    try:
        for seg_idx, segmento in enumerate(segmentos):
            batch_procesar = []

            for celda in segmento:
                tile = geo.leer_tile_filtrado(celda["x"], celda["y"], celda["ancho"], celda["alto"])
                if tile is not None:
                    batch_procesar.append((celda, tile))

            detecciones_bloque = detector.procesar_lote_celdas(batch_procesar)
            estructura_datos["detecciones"].extend(detecciones_bloque)

            progreso_pct = round(((seg_idx + 1) / len(segmentos)) * 100, 1)
            estructura_datos["progreso_actual_pct"] = progreso_pct
            estructura_datos["bloques_procesados"] = seg_idx + 1

            print(f"-> Bloque {seg_idx + 1}/{len(segmentos)} completado ({progreso_pct}%) | "
                  f"Activas: {len(batch_procesar)}/{len(segmento)} celdas | "
                  f"Detecciones en segmento: {len(detecciones_bloque)} | "
                  f"Acumuladas: {len(estructura_datos['detecciones'])}")

            # Payload que viaja al frontend en cada 10%
            chunk = {
                "bloque": seg_idx + 1,
                "total_bloques": len(segmentos),
                "progreso_pct": progreso_pct,
                "activas": len(batch_procesar),
                "detecciones": detecciones_bloque,
                "total_acumuladas": len(estructura_datos["detecciones"])
            }
            yield chunk

    except KeyboardInterrupt:
        print("\n[AVISO] Proceso detenido manualmente por el usuario.")
    
    finally:
        geo.cerrar()
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(estructura_datos, f, indent=2)
        print(f"[GUARDADO] JSON final/parcial actualizado con {len(estructura_datos['detecciones'])} detecciones en: {ruta_json}")

if __name__ == "__main__":
    # Si se ejecuta directo por terminal, consume el generador bloque a bloque
    for _ in ejecutar_inspeccion_segmentada("El Azul_COG.tif", cuadrante=3):
        pass