from transformers import pipeline
import os

def test_plant_specialist(img_path):
    print("\n--- [TEST 3: Plant Specialist (ViT-Base)] ---")
    
    # 1. Usamos un modelo de Google que es el estándar para Vision Transformers
    print("Cargando modelo de Google... (Aprox. 300MB, paciencia la primera vez)")
    try:
        # Este modelo es muy bueno reconociendo estructuras generales
        classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
        
        print(f"Analizando imagen: {os.path.basename(img_path)}")
        results = classifier(img_path)
        
        print("\n--- TOP DETECCIONES ---")
        for res in results[:3]:
            porcentaje = round(res['score'] * 100, 2)
            label = res['label'].replace('_', ' ')
            print(f"Detección: {label} ({porcentaje}%)")
            
    except Exception as e:
        print(f"Error específico al cargar el modelo: {e}")

if __name__ == "__main__":
    # Aseguramos que la ruta sea la correcta en tu D:
    IMAGEN = r"D:/imagenes de ejemplo/test.jpg" 
    
    if os.path.exists(IMAGEN):
        test_plant_specialist(IMAGEN)
    else:
        print(f"Error: No se encontró el archivo en: {IMAGEN}")
