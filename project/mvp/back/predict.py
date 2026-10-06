import json
import math
from geo import GeoHandler
from detector import FieldDetector

def ejecutar_inspeccion_segmentada(ruta_tif, cuadrante=3, ruta_json="detecciones_campo.json", conf=0.10):
    """
    Generador que procesa el ortomosaico en 10 bloques.
    En cada iteración emite (yield) un diccionario con el progreso y 
    las nuevas detecciones del bloque para que la API las envíe al front.
    """
    geo = GeoHandler(ruta_tif, tamano_tile=640)
    detector = FieldDetector(conf_threshold=conf)
    
    celdas = geo.obtener_lista_cuadrantes(cuadrante=cuadrante)
    total_celdas = len(celdas)
    
    tamano_segmento = max(1, math.ceil(total_celdas / 10))
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

    print(f"[INICIO] {total_celdas} celdas divididas en {len(segmentos)} bloques (~10% c/u).")

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