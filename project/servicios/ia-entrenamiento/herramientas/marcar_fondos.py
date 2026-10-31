"""
Marca imágenes como fondo (ejemplo negativo) escribiéndoles un JSON de labelme sin formas.

labelme no guarda una imagen en la que no se dibujó nada, y una imagen sin JSON
el aporte la ignora como posible descuido. Este script escribe ese JSON vacío
al lado de cada imagen indicada; las que ya tienen JSON no se tocan.

Uso:
    python marcar_fondos.py lote_008/tile_x1_y2.jpg lote_008/tile_x3_y4.jpg
"""
import json
import sys
from pathlib import Path

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def marcar_fondo(imagen: Path) -> str:
    if imagen.suffix.lower() not in EXTENSIONES_IMAGEN or not imagen.is_file():
        return f"omitida (no es una imagen): {imagen}"
    destino = imagen.with_suffix(".json")
    if destino.exists():
        return f"omitida (ya tiene JSON): {imagen}"
    destino.write_text(json.dumps({
        "version": "5.10.1",
        "flags": {},
        "shapes": [],
        "imagePath": imagen.name,
        "imageData": None,
    }, indent=2), encoding="utf-8")
    return f"marcada como fondo: {imagen}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for argumento in sys.argv[1:]:
        print(marcar_fondo(Path(argumento)))
