import os
import shutil
import tempfile
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from collections import Counter
import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from ultralytics import YOLO

# ==========================================
# 1. PARSEO DE COORDENADAS GPS DESDE EXIF
# ==========================================
def _convertir_a_grados(valor):
    d = float(valor[0])
    m = float(valor[1])
    s = float(valor[2])
    return d + (m / 60.0) + (s / 3600.0)

def extraer_gps(ruta_imagen):
    try:
        with Image.open(ruta_imagen) as img:
            exif_raw = img._getexif()
            if not exif_raw:
                return None, None

            gps_info = {}
            for tag_id, valor in exif_raw.items():
                nombre_tag = TAGS.get(tag_id, tag_id)
                if nombre_tag == "GPSInfo":
                    for key, sub_val in valor.items():
                        sub_tag = GPSTAGS.get(key, key)
                        gps_info[sub_tag] = sub_val

            if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
                lat = _convertir_a_grados(gps_info["GPSLatitude"])
                lon = _convertir_a_grados(gps_info["GPSLongitude"])

                if gps_info.get("GPSLatitudeRef") == "S":
                    lat = -lat
                if gps_info.get("GPSLongitudeRef") == "W":
                    lon = -lon
                return lat, lon
    except Exception as e:
        print(f"Error leyendo EXIF en {ruta_imagen}: {e}")
    return None, None

# ==========================================
# 2. CONSTRUCCIÓN DE LA MATRIZ ESPACIAL
# ==========================================
def construir_matriz_campo(lista_datos, tolerancia_deg=0.0003):
    lista_datos = sorted(lista_datos, key=lambda x: x["lat"], reverse=True)
    filas = []
    fila_actual = []
    lat_referencia = None

    for item in lista_datos:
        if lat_referencia is None:
            lat_referencia = item["lat"]
            fila_actual.append(item)
        elif abs(item["lat"] - lat_referencia) <= tolerancia_deg:
            fila_actual.append(item)
        else:
            fila_actual = sorted(fila_actual, key=lambda x: x["lon"])
            filas.append(fila_actual)
            fila_actual = [item]
            lat_referencia = item["lat"]

    if fila_actual:
        fila_actual = sorted(fila_actual, key=lambda x: x["lon"])
        filas.append(fila_actual)

    return filas

# ==========================================
# 3. GENERACIÓN DEL COLLAGE MATRICIAL
# ==========================================
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

            if c_idx < len(fila):
                im_redim = cv2.resize(fila[c_idx], (ancho_celda, alto_celda))
                cv2.rectangle(im_redim, (0, 0), (ancho_celda - 1, alto_celda - 1), (50, 50, 50), 1)
                collage[y1:y2, x1:x2] = im_redim
            else:
                celda_vacia = np.zeros((alto_celda, ancho_celda, 3), dtype=np.uint8)
                cv2.putText(celda_vacia, "Vacio", (int(ancho_celda/2) - 40, int(alto_celda/2)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 2)
                collage[y1:y2, x1:x2] = celda_vacia

    return collage

# ==========================================
# 4. CLASE PRINCIPAL DE LA APLICACIÓN (GUI)
# ==========================================
class AppInspeccionDron:
    def __init__(self, root):
        self.root = root
        self.root.title("Panel de Inspección Agrícola - YOLOv8")
        self.root.geometry("820x520")
        self.root.resizable(False, False)

        self._crear_interfaz()

    def _crear_interfaz(self):
        # Panel izquierdo (Controles)
        frame_izq = tk.Frame(self.root, width=320, padx=15, pady=15)
        frame_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        titulo = tk.Label(frame_izq, text="Vuelo y Detección", font=("Helvetica", 12, "bold"))
        titulo.pack(pady=5)

        subtitulo = tk.Label(frame_izq, text="Seleccione imágenes aéreas con GPS:", font=("Helvetica", 9))
        subtitulo.pack(pady=5)

        btn_carpeta = tk.Button(
            frame_izq, text="📁 Seleccionar Carpeta", font=("Helvetica", 10),
            command=self.seleccionar_carpeta, width=26, height=1
        )
        btn_carpeta.pack(pady=8)

        btn_zip = tk.Button(
            frame_izq, text="📦 Seleccionar Archivo .ZIP", font=("Helvetica", 10),
            command=self.seleccionar_archivo_zip, width=26, height=1
        )
        btn_zip.pack(pady=8)

        # Barra separadora
        sep = ttk.Separator(self.root, orient="vertical")
        sep.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=10)

        # Panel derecho (Dashboard de métricas)
        frame_der = tk.LabelFrame(self.root, text=" Estadísticas y Detecciones en Tiempo Real ", padx=12, pady=12, font=("Helvetica", 10, "bold"))
        frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 1. Progreso
        self.lbl_progreso = tk.Label(frame_der, text="Progreso: 0 imágenes analizadas (0%)", font=("Helvetica", 9, "bold"), anchor="w")
        self.lbl_progreso.pack(fill=tk.X, pady=3)

        # 2. Objetos encontrados y porcentajes
        self.lbl_objetos = tk.Label(frame_der, text="Objetos encontrados: Ninguno", font=("Helvetica", 9), anchor="w", justify=tk.LEFT)
        self.lbl_objetos.pack(fill=tk.X, pady=2)

        self.lbl_porcentajes = tk.Label(frame_der, text="Distribución de objetos: N/A", font=("Helvetica", 9), fg="#2c3e50", anchor="w", justify=tk.LEFT)
        self.lbl_porcentajes.pack(fill=tk.X, pady=2)

        # 3. Log de aciertos por imagen
        lbl_log = tk.Label(frame_der, text="Probabilidad de acierto por imagen:", font=("Helvetica", 9, "bold"), anchor="w")
        lbl_log.pack(fill=tk.X, pady=(10, 2))

        self.txt_log = ScrolledText(frame_der, height=14, font=("Consolas", 8))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def seleccionar_carpeta(self):
        ruta = filedialog.askdirectory(title="Seleccionar Carpeta con Imágenes de Dron")
        if ruta:
            self.procesar_origen(ruta)

    def seleccionar_archivo_zip(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Archivo Comprimido",
            filetypes=[("Archivos ZIP", "*.zip"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            self.procesar_origen(ruta)

    def procesar_origen(self, ruta_origen):
        directorio_trabajo = None
        es_temporal = False

        if os.path.isfile(ruta_origen) and ruta_origen.lower().endswith(".zip"):
            directorio_trabajo = tempfile.mkdtemp()
            es_temporal = True
            with zipfile.ZipFile(ruta_origen, 'r') as zip_ref:
                zip_ref.extractall(directorio_trabajo)
            ruta_escaneo = Path(directorio_trabajo)
        elif os.path.isdir(ruta_origen):
            ruta_escaneo = Path(ruta_origen)
        else:
            messagebox.showerror("Error", "Formato no compatible.")
            return

        archivos = [p for p in ruta_escaneo.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}]
        if not archivos:
            messagebox.showwarning("Sin imágenes", "No se encontraron imágenes en el origen seleccionado.")
            if es_temporal:
                shutil.rmtree(directorio_trabajo)
            return

        # Extraer GPS
        datos_imagenes = []
        for ruta in archivos:
            lat, lon = extraer_gps(ruta)
            if lat is not None and lon is not None:
                datos_imagenes.append({"ruta": str(ruta), "lat": lat, "lon": lon})

        if not datos_imagenes:
            messagebox.showerror("Sin GPS", f"Se encontraron {len(archivos)} imágenes, pero ninguna contiene coordenadas GPS en sus metadatos EXIF.")
            if es_temporal:
                shutil.rmtree(directorio_trabajo)
            return

        matriz = construir_matriz_campo(datos_imagenes)
        total_imagenes = sum(len(fila) for fila in matriz)

        # Cargar modelo
        modelo_path = "runs/detect/train-2/weights/best.pt"
        if not os.path.exists(modelo_path):
            messagebox.showerror("Error", f"No se encontró el modelo en: {modelo_path}")
            if es_temporal:
                shutil.rmtree(directorio_trabajo)
            return

        model = YOLO(modelo_path)

        # Reiniciar métricas visuales
        self.txt_log.delete("1.0", tk.END)
        self.lbl_progreso.config(text=f"Progreso: 0/{total_imagenes} (0%)")
        self.root.update()

        matriz_imagenes_procesadas = []
        contador_clases = Counter()
        analizadas_cuenta = 0

        for r_idx, fila in enumerate(matriz):
            fila_imgs = []
            for c_idx, celda in enumerate(fila):
                analizadas_cuenta += 1
                img_path = celda["ruta"]
                nombre_foto = Path(img_path).name
                lat, lon = celda["lat"], celda["lon"]

                results = model.predict(source=img_path, conf=0.15, save=False, verbose=False)

                for result in results:
                    im_bgr = result.plot()
                    total_detecciones = len(result.boxes)

                    info_texto = f"[{r_idx},{c_idx}] Det:{total_detecciones} ({lat:.4f},{lon:.4f})"
                    cv2.rectangle(im_bgr, (5, 5), (380, 35), (0, 0, 0), -1)
                    cv2.putText(im_bgr, info_texto, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                    fila_imgs.append(im_bgr)

                    # Registrar detecciones individuales de esta imagen
                    if total_detecciones > 0:
                        reporte_foto = []
                        for box in result.boxes:
                            cls_id = int(box.cls[0])
                            clase_nombre = model.names[cls_id]
                            confianza_pct = float(box.conf[0]) * 100
                            contador_clases[clase_nombre] += 1
                            reporte_foto.append(f"{clase_nombre} ({confianza_pct:.1f}% acierto)")

                        linea_log = f"• {nombre_foto}: " + ", ".join(reporte_foto) + "\n"
                    else:
                        linea_log = f"• {nombre_foto}: Sin detecciones\n"

                    self.txt_log.insert(tk.END, linea_log)
                    self.txt_log.see(tk.END)

                # Actualizar progreso
                porcentaje_progreso = (analizadas_cuenta / total_imagenes) * 100
                self.lbl_progreso.config(text=f"Progreso: {total_imagenes} imágenes, {analizadas_cuenta} analizadas ({porcentaje_progreso:.1f}%)")

                # Actualizar objetos encontrados y sus porcentajes
                total_objetos = sum(contador_clases.values())
                if total_objetos > 0:
                    lista_objs_texto = ", ".join([f"{cls} ({cant})" for cls, cant in contador_clases.items()])
                    self.lbl_objetos.config(text=f"Objetos encontrados: {lista_objs_texto}")

                    distribucion_texto = ", ".join([
                        f"{(cant / total_objetos) * 100:.1f}% {cls}" for cls, cant in contador_clases.items()
                    ])
                    self.lbl_porcentajes.config(text=f"Porcentaje de cada objeto: {distribucion_texto}")

                self.root.update()

            matriz_imagenes_procesadas.append(fila_imgs)

        # Generar y mostrar collage
        collage_final = generar_collage(matriz_imagenes_procesadas)
        cv2.imwrite("collage_geolocalizado.jpg", collage_final)

        cv2.namedWindow("Mapa Completo - Collage Espacial", cv2.WINDOW_NORMAL)
        cv2.imshow("Mapa Completo - Collage Espacial", collage_final)
        cv2.waitKey(1)

        messagebox.showinfo("Completado", "Inspección completada con éxito. Collage guardado como 'collage_geolocalizado.jpg'.")

        if es_temporal:
            shutil.rmtree(directorio_trabajo)

def main():
    root = tk.Tk()
    app = AppInspeccionDron(root)
    root.mainloop()

if __name__ == "__main__":
    main()