from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
from PIL import Image
import os

def test_inaturalist(img_path):
    print("\n--- [TEST 1: Especialista en Flora] ---")
    
    # CAMBIAMOS EL REPO AQUÍ:
    repo = "google/vit-base-patch16-224" 
    
    print(f"Cargando {repo}...")
    processor = AutoImageProcessor.from_pretrained(repo)
    model = AutoModelForImageClassification.from_pretrained(repo)

    # 2. Procesar la imagen
    img = Image.open(img_path).convert('RGB')
    inputs = processor(images=img, return_tensors="pt")

    # 3. Realizar la predicción
    print("Analizando texturas botánicas...")
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class_idx = logits.argmax(-1).item()
        
    print(f"Resultado: {model.config.id2label[predicted_class_idx]}")

# IMPORTANTE: Este bloque debe ir SIN espacios al principio
if __name__ == "__main__":
    ruta = r"D:/imagenes de ejemplo/test.jpg" # Asegurate que el archivo esté ahí
    
    if os.path.exists(ruta):
        test_inaturalist(ruta)
    else:
        print(f"Error: No se encontró la imagen en {ruta}")