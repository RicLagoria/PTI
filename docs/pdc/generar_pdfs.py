"""
Genera los PDF de cada entrega a partir de los Markdown de docs/pdc/.

Renderiza el Markdown (marked) y los diagramas (mermaid) en un Chrome/Edge sin
interfaz y lo imprime a PDF. Necesita conexión para bajar esas dos librerías.

Uso:  python docs/pdc/generar_pdfs.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
SALIDA = CARPETA / "pdf"

DOCUMENTOS = [
    ("entrega-0-plan/README.md", "Tarea0-Plan-del-proyecto-COMPLETA.pdf"),
    ("entrega-1-arquitectura/README.md", "Tarea1-Certificado-COMPLETO.pdf"),
    ("entrega-1-arquitectura/informe.md", "Tarea1-Informe-Arquitectura-4+1.pdf"),
    ("entrega-2-infraestructura/README.md", "Tarea2-Certificado-COMPLETO.pdf"),
    ("entrega-2-infraestructura/informe.md", "Tarea2-Informe-Infraestructura.pdf"),
]

NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chromium-browser",
]

PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<base href="__BASE__">
<style>
  @page { size: A4; margin: 16mm 15mm 18mm; }
  body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.5pt; color: #1d1d1b; line-height: 1.45; }
  h1, h2, h3 { page-break-after: avoid; break-after: avoid; }
  h1 { font-size: 17pt; border-bottom: 2.5px solid #1d1d1b; padding-bottom: 6px; margin: 0 0 10px; }
  h2 { font-size: 13pt; margin: 20px 0 8px; color: #2f5d27; border-bottom: 1px solid #d7d7cf; padding-bottom: 3px; }
  h3 { font-size: 11.5pt; margin: 14px 0 6px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.5pt; page-break-inside: auto; }
  tr { page-break-inside: avoid; }
  th, td { border: 1px solid #c9c9c0; padding: 5px 7px; vertical-align: top; text-align: left; }
  th { background: #eef0e8; }
  code { font-family: Consolas, monospace; font-size: 9pt; background: #f2f2ee; padding: 1px 3px; border-radius: 3px; }
  pre { background: #f5f5f1; border: 1px solid #deded6; padding: 8px 10px; font-size: 8.5pt; white-space: pre-wrap; page-break-inside: avoid; }
  pre code { background: none; padding: 0; }
  blockquote { margin: 8px 0; padding: 6px 12px; border-left: 4px solid #3f6b34; background: #f1f5ee; color: #333; }
  img { max-width: 100%; display: block; margin: 8px auto; page-break-inside: avoid; }
  .mermaid { text-align: center; margin: 10px 0; page-break-inside: avoid; }
  .mermaid svg { max-width: 100% !important; height: auto; }
  a { color: #2f5d27; }
  hr { border: 0; border-top: 1px solid #ccc; margin: 18px 0; }
</style></head>
<body>
<div id="contenido"></div>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>
  const md = __MARKDOWN__;
  const renderer = new marked.Renderer();
  const codigoOriginal = renderer.code.bind(renderer);
  renderer.code = (code, lang, escaped) =>
    lang === "mermaid" ? '<div class="mermaid">' + code + "</div>" : codigoOriginal(code, lang, escaped);
  document.getElementById("contenido").innerHTML = marked.parse(md, { renderer });
  mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose",
                       flowchart: { htmlLabels: true }, gantt: { barHeight: 16, fontSize: 10 } });
  mermaid.run();
</script>
</body></html>
"""


def buscar_navegador():
    for candidato in NAVEGADORES:
        if os.path.isfile(candidato) or shutil.which(candidato):
            return candidato
    sys.exit("No se encontró Chrome ni Edge para imprimir los PDF.")


def generar(navegador, origen, destino):
    ruta_md = CARPETA / origen
    html = (PLANTILLA
            .replace("__BASE__", ruta_md.parent.as_uri() + "/")
            .replace("__MARKDOWN__", json.dumps(ruta_md.read_text(encoding="utf-8"))))
    temporal = ruta_md.parent / "_render.html"
    temporal.write_text(html, encoding="utf-8")
    try:
        subprocess.run([
            navegador, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
            "--virtual-time-budget=15000", "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={SALIDA / destino}", temporal.as_uri(),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        temporal.unlink(missing_ok=True)
    print(f"OK  {destino}")


if __name__ == "__main__":
    SALIDA.mkdir(exist_ok=True)
    navegador = buscar_navegador()
    for origen, destino in DOCUMENTOS:
        generar(navegador, origen, destino)
