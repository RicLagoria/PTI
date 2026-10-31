"""
Informe en PDF de un análisis: a diferencia de exportar.geojson/.csv (que son
puros datos), esto arma algo para mirar — la imagen del campo con las
detecciones marcadas encima, más un resumen. Usa el mismo COG que ya está en
disco (ver almacen.py), no vuelve a pedir nada a ia-inferencia.
"""
import io
from datetime import datetime, timezone
from typing import Dict, List

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles

COLOR_POR_CLASE = {
    "maleza": (239, 68, 68),
    "falla": (245, 158, 11),
    "camino": (100, 116, 139),
    "lodazal": (14, 165, 233),
}
COLOR_DEFECTO = (167, 139, 250)

ESTADO_LABEL = {"completo": "Completo", "en_progreso": "En progreso", "error": "Error"}


def _color_de(clase: str) -> tuple:
    return COLOR_POR_CLASE.get(clase, COLOR_DEFECTO)


def _imagen_con_marcas(ruta_archivo: str, ancho_px: int, alto_px: int, detecciones: List[Dict]) -> Image.Image:
    """Preview del COG completo (liviano, no la imagen original de gigas) con
    un punto por detección, reproyectando box_global_px a la escala del preview."""
    with Reader(ruta_archivo) as cog:
        preview = cog.preview(max_size=1100)
        png_bytes = preview.render(img_format="PNG", **img_profiles.get("png"))

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    dibujo = ImageDraw.Draw(img)
    escala_x = img.width / ancho_px
    escala_y = img.height / alto_px

    for det in detecciones:
        x1, y1, x2, y2 = det["box_global_px"][:4]
        cx = (x1 + x2) / 2 * escala_x
        cy = (y1 + y2) / 2 * escala_y
        r = 5
        dibujo.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_color_de(det["clase"]), outline=(255, 255, 255), width=1)

    return img


def generar_pdf(ortomosaico: Dict, analisis: Dict, detecciones: List[Dict], usuario_nombre: str) -> bytes:
    estilos = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=15 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    elementos = []

    elementos.append(Paragraph(f"Informe de análisis — {ortomosaico['nombre']}", estilos["Title"]))
    elementos.append(Paragraph(f"Análisis #{analisis['id']} · AgroVision", estilos["Normal"]))
    elementos.append(Spacer(1, 6 * mm))

    fecha_inicio = analisis["fecha_inicio"]
    fecha_texto = fecha_inicio.strftime("%d/%m/%Y %H:%M") if hasattr(fecha_inicio, "strftime") else str(fecha_inicio)[:16].replace("T", " ")

    filas_meta = [
        ["Ortomosaico", ortomosaico["nombre"]],
        ["Subido por", ortomosaico.get("usuario_nombre") or "—"],
        ["Fecha del análisis", fecha_texto],
        ["Corrido por", usuario_nombre or "—"],
        ["Versión del modelo", analisis["version_modelo"]],
        ["Confianza mínima", f"{round(analisis['conf_umbral'] * 100)}%"],
        ["Estado", ESTADO_LABEL.get(analisis["estado"], analisis["estado"])],
        ["Celdas inspeccionadas", f"{analisis.get('celdas_activas') or 0} / {analisis.get('total_celdas') or 0}"],
        ["Detecciones totales", str(len(detecciones))],
    ]
    tabla_meta = Table(filas_meta, colWidths=[55 * mm, 110 * mm])
    tabla_meta.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
    ]))
    elementos.append(tabla_meta)
    elementos.append(Spacer(1, 6 * mm))

    if detecciones:
        img = _imagen_con_marcas(ortomosaico["ruta_archivo"], ortomosaico["ancho_px"], ortomosaico["alto_px"], detecciones)
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        ancho_doc = doc.width
        alto_img = ancho_doc * img.height / img.width
        elementos.append(RLImage(img_buffer, width=ancho_doc, height=alto_img))
        elementos.append(Spacer(1, 6 * mm))

        conteo: Dict[str, Dict] = {}
        for d in detecciones:
            c = conteo.setdefault(d["clase"], {"cantidad": 0, "suma_confianza": 0.0})
            c["cantidad"] += 1
            c["suma_confianza"] += d["confianza"]

        filas_clase = [["", "Clase", "Cantidad", "Confianza prom."]]
        for clase, c in sorted(conteo.items(), key=lambda kv: -kv[1]["cantidad"]):
            filas_clase.append(["", clase, str(c["cantidad"]), f"{round(100 * c['suma_confianza'] / c['cantidad'])}%"])

        tabla_clases = Table(filas_clase, colWidths=[6 * mm, 60 * mm, 30 * mm, 35 * mm])
        estilo_clases = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#64748b")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#94a3b8")),
        ]
        for i, (clase, _) in enumerate(sorted(conteo.items(), key=lambda kv: -kv[1]["cantidad"]), start=1):
            r, g, b = _color_de(clase)
            estilo_clases.append(("BACKGROUND", (0, i), (0, i), colors.Color(r / 255, g / 255, b / 255)))
        tabla_clases.setStyle(TableStyle(estilo_clases))
        elementos.append(tabla_clases)
    else:
        elementos.append(Paragraph("Este análisis no encontró detecciones.", estilos["Normal"]))

    elementos.append(Spacer(1, 10 * mm))
    pie = f"Generado por AgroVision el {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}"
    elementos.append(Paragraph(pie, estilos["Italic"]))

    doc.build(elementos)
    return buffer.getvalue()
