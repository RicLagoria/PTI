import cv2
import numpy as np

class Visualizer:
    @staticmethod
    def generar_collage(matriz_procesada, ancho_celda=400, alto_celda=300):
        num_filas = len(matriz_procesada)
        max_columnas = max(len(fila) for fila in matriz_procesada)

        alto_total = num_filas * alto_celda
        ancho_total = max_columnas * ancho_celda
        collage = np.zeros((alto_total, ancho_total, 3), dtype=np.uint8)

        for r_idx, fila in enumerate(matriz_procesada):
            for c_idx in range(max_columnas):
                y1 = r_idx * alto_celda
                y2 = y1 + alto_celda
                x1 = c_idx * ancho_celda
                x2 = x1 + ancho_celda

                if c_idx < len(fila) and fila[c_idx] is not None:
                    im_redim = cv2.resize(fila[c_idx], (ancho_celda, alto_celda))
                    cv2.rectangle(im_redim, (0, 0), (ancho_celda - 1, alto_celda - 1), (50, 50, 50), 1)
                    collage[y1:y2, x1:x2] = im_redim
                else:
                    celda_vacia = np.zeros((alto_celda, ancho_celda, 3), dtype=np.uint8)
                    cv2.putText(celda_vacia, "Vacio", (int(ancho_celda/2) - 40, int(alto_celda/2)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
                    collage[y1:y2, x1:x2] = celda_vacia

        return collage

    @staticmethod
    def generar_heatmap(matriz_densidad, ruta_salida="heatmap_lote.jpg"):
        norm = cv2.normalize(matriz_densidad.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX)
        heatmap = cv2.applyColorMap(norm.astype(np.uint8), cv2.COLORMAP_JET)
        heatmap_grande = cv2.resize(heatmap, (600, 400), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(ruta_salida, heatmap_grande)
        return heatmap_grande