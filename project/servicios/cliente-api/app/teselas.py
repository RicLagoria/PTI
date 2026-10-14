from pathlib import Path
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles


def renderizar_tesela_png(ruta_cog: Path, z: int, x: int, y: int) -> bytes:
    """
    Lee bajo demanda únicamente los píxeles necesarios para el nivel de zoom Z
    y coordenadas X/Y directamente desde la estructura COG y devuelve un PNG.
    """
    with Reader(str(ruta_cog)) as cog:
        img = cog.tile(x, y, z, tilesize=256)
        return img.render(img_format="PNG", **img_profiles.get("png"))

