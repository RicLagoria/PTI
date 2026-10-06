import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
from PIL import Image
import os
import urllib.request

def get_labels():
    # Descargamos el mapeo de nombres de Google
    label_url = "https://www.gstatic.com/aihub/tfhub/labelmaps/aiy_plants_V1_labelmap.csv"
    labels = {}
    try:
        with urllib.request.urlopen(label_url) as response:
            lines = response.read().decode('utf-8').splitlines()
            for line in lines[1:]: # Saltamos la cabecera
                id_str, name = line.split(',', 1)
                labels[int(id_str)] = name.strip()
    except:
        print("No se pudo descargar el mapa de nombres. Usando IDs genéricos.")
    return labels

def test_google_agritech(img_path):
    print("\n--- [TEST 2: Google AgriTech (Botánica)] ---")
    
    # 1. Cargar el modelo desde TF Hub
    model_url = "https://tfhub.dev/google/aiy/vision/classifier/plants_V1/1"
    print("Cargando motor botánico de Google...")
    model = hub.KerasLayer(model_url)

    # 2. Preprocesar la imagen
    img = Image.open(img_path).convert('RGB').resize((224, 224))
    img_array = np.array(img) / 255.0
    img_array = img_array[np.newaxis, ...]

    # 3. Predicción
    predictions = model(img_array)
    top_index = np.argmax(predictions)
    probabilidad = np.max(predictions)

    # 4. Traducir ID a Nombre
    labels = get_labels()
    nombre_especie = labels.get(top_index, "Desconocido")

    print(f"ID Detectado: {top_index}")
    print(f"Especie probable: {nombre_especie}")
    print(f"Confianza: {probabilidad:.2f}")

if __name__ == "__main__":
    IMAGEN = r"D:/imagenes de ejemplo/test.jpg" 
    
    if os.path.exists(IMAGEN):
        try:
            test_google_agritech(IMAGEN)
        except Exception as e: 
            print(f"Error en el modelo: {e}")
    else:
        print(f"No se encontró la imagen en: {IMAGEN}")