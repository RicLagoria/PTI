import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from collections import Counter
import cv2
import numpy as np

# Importaciones directas (mismo nivel de carpeta)
from geo import GeoHandler
from detector import FieldDetector
from visual import Visualizer

class AppInspeccionDron:
    def __init__(self, root):
        self.root = root
        self.root.title("Inspección Agrícola - Ortomosaicos YOLOv8")
        self.root.geometry("860x540")
        self.root.resizable(False, False)

        self._crear_interfaz()

    def _crear_interfaz(self):
        frame_izq = tk.Frame(self.root, width=320, padx=15, pady=15)
        frame_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        titulo = tk.Label(frame_izq, text="Panel de Control", font=("Helvetica", 12, "bold"))
        titulo.pack(pady=5)

        subtitulo = tk.Label(frame_izq, text="Seleccione el ortomosaico (.tif):", font=("Helvetica", 9))
        subtitulo.pack(pady=5)

        btn_tif = tk.Button(
            frame_izq, text="🗺️ Seleccionar GeoTIFF (.tif)", font=("Helvetica", 10),
            command=self.seleccionar_ortomosaico, width=26, height=2
        )
        btn_tif.pack(pady=15)

        sep = ttk.Separator(self.root, orient="vertical")
        sep.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=10)

        frame_der = tk.LabelFrame(self.root, text=" Estadísticas y Métricas ", padx=12, pady=12, font=("Helvetica", 10, "bold"))
        frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.lbl_info = tk.Label(frame_der, text="Dimensiones: Esperando archivo...", font=("Helvetica", 9), anchor="w")
        self.lbl_info.pack(fill=tk.X, pady=2)

        self.lbl_progreso = tk.Label(frame_der, text="Progreso: 0 cuadrantes (0%)", font=("Helvetica", 9, "bold"), anchor="w")
        self.lbl_progreso.pack(fill=tk.X, pady=3)

        self.lbl_objetos = tk.Label(frame_der, text="Objetos encontrados: Ninguno", font=("Helvetica", 9), anchor="w")
        self.lbl_objetos.pack(fill=tk.X, pady=2)

        self.lbl_porcentajes = tk.Label(frame_der, text="Distribución: N/A", font=("Helvetica", 9), fg="#2c3e50", anchor="w")
        self.lbl_porcentajes.pack(fill=tk.X, pady=2)

        lbl_log = tk.Label(frame_der, text="Registro por cuadrante:", font=("Helvetica", 9, "bold"), anchor="w")
        lbl_log.pack(fill=tk.X, pady=(10, 2))

        self.txt_log = ScrolledText(frame_der, height=14, font=("Consolas", 8))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def seleccionar_ortomosaico(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Ortomosaico GeoTIFF",
            filetypes=[("Archivos TIFF", "*.tif;*.tiff"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            self.procesar(ruta)

    def procesar(self, ruta_tif):
        tamano_tile = 640
        geo = GeoHandler(ruta_tif, tamano_tile=tamano_tile)
        matriz_espacial = geo.obtener_matriz_espacial()
        total_cuadrantes = geo.filas * geo.columnas

        self.lbl_info.config(
            text=f"Dimensiones: {geo.ancho_total}x{geo.alto_total} px | Matriz: {geo.filas}x{geo.columnas} ({total_cuadrantes} cuadrantes)"
        )

        modelo_path = "runs/detect/train-2/weights/best.pt"
        if not os.path.exists(modelo_path):
            messagebox.showerror("Error", f"No se encontró el modelo en: {modelo_path}")
            geo.cerrar()
            return

        detector = FieldDetector(model_path=modelo_path, conf_threshold=0.15)

        self.txt_log.delete("1.0", tk.END)
        contador_clases = Counter()
        analizados = 0

        matriz_densidad = np.zeros((geo.filas, geo.columnas), dtype=np.int32)
        matriz_imagenes_procesadas = []

        for r in range(geo.filas):
            fila_imgs = []
            for c in range(geo.columnas):
                analizados += 1
                celda = matriz_espacial[r][c]
                x, y, w, h = celda["bounds_px"]
                lat, lon = celda["gps_centro"]

                tile = geo.leer_tile(x, y, w, h)

                if tile.mean() < 10:
                    fila_imgs.append(None)
                    continue

                detecciones, img_anotada = detector.predecir_tile(tile)
                matriz_densidad[r, c] = len(detecciones)

                # Estampar etiqueta informativa
                info_texto = f"[{r},{c}] Det:{len(detecciones)} ({lat:.4f},{lon:.4f})"
                cv2.rectangle(img_anotada, (5, 5), (380, 35), (0, 0, 0), -1)
                cv2.putText(img_anotada, info_texto, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                fila_imgs.append(img_anotada)

                if detecciones:
                    reportes = []
                    for d in detecciones:
                        contador_clases[d["clase"]] += 1
                        reportes.append(f"{d['clase']} ({d['confianza']:.1f}%)")
                    linea = f"• Cuadrante [{r},{c}] GPS({lat:.4f},{lon:.4f}): " + ", ".join(reportes) + "\n"
                else:
                    linea = f"• Cuadrante [{r},{c}] GPS({lat:.4f},{lon:.4f}): Limpio\n"

                self.txt_log.insert(tk.END, linea)
                self.txt_log.see(tk.END)

                # Actualizar métricas GUI
                pct = (analizados / total_cuadrantes) * 100
                self.lbl_progreso.config(text=f"Progreso: {total_cuadrantes} cuadrantes, {analizados} analizados ({pct:.1f}%)")

                total_objs = sum(contador_clases.values())
                if total_objs > 0:
                    self.lbl_objetos.config(
                        text="Objetos: " + ", ".join([f"{k} ({v})" for k, v in contador_clases.items()])
                    )
                    distrib = ", ".join([f"{(v/total_objs)*100:.1f}% {k}" for k, v in contador_clases.items()])
                    self.lbl_porcentajes.config(text=f"Distribución: {distrib}")

                self.root.update()

            matriz_imagenes_procesadas.append(fila_imgs)

        geo.cerrar()

        # Generar collage y mapa de calor
        collage = Visualizer.generar_collage(matriz_imagenes_procesadas)
        cv2.imwrite("collage_lote.jpg", collage)

        heatmap = Visualizer.generar_heatmap(matriz_densidad, "heatmap_lote.jpg")

        cv2.namedWindow("Collage Completo", cv2.WINDOW_NORMAL)
        cv2.imshow("Collage Completo", collage)

        cv2.namedWindow("Mapa de Severidad (Heatmap)", cv2.WINDOW_NORMAL)
        cv2.imshow("Mapa de Severidad (Heatmap)", heatmap)
        cv2.waitKey(1)

        messagebox.showinfo("Completado", "Análisis finalizado.\nArchivos guardados: 'collage_lote.jpg' y 'heatmap_lote.jpg'.")

def main():
    root = tk.Tk()
    app = AppInspeccionDron(root)
    root.mainloop()

if __name__ == "__main__":
    main()