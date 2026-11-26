"""
Prueba de autorización por rol contra cliente-api (Entrega 5 de PDC).

Entra con la cuenta `lector` y con una `colaborador`, y hace los mismos pedidos
con las dos. Lo que se espera:

  - Leer (listar imágenes, estadísticas): las dos pueden -> 200.
  - Subir un ortomosaico o correr un análisis: el lector recibe 403;
    el colaborador pasa el control de rol (después puede fallar por otra cosa,
    p. ej. 404 porque la imagen de prueba no existe, pero NO 403).
  - Sin token: 401.

Uso:
    python docs/pdc/entrega-5-seguridad/probar_roles.py                         # por el gateway HTTPS (compose.pdc.yml)
    python docs/pdc/entrega-5-seguridad/probar_roles.py http://localhost:8000   # directo, solo compose.dev.yml
"""
import json
import ssl
import sys
from pathlib import Path
import urllib.error
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "https://localhost/api"
# El certificado del gateway es autofirmado: en vez de apagar la verificación,
# le decimos a Python que confíe en ese certificado puntual.
CERT = Path(__file__).resolve().parents[3] / "despliegue/nginx/certs/agrovision.crt"
CONTEXTO = ssl.create_default_context(cafile=str(CERT)) if CERT.exists() else None
CUENTAS = {"lector": "Lector2026!", "santigodoy52": "Santiago2026!"}
IMAGEN_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


def pedir(metodo, ruta, token=None, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(API + ruta, data=datos, method=metodo)
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, context=CONTEXTO) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def entrar(usuario, contrasena):
    req = urllib.request.Request(
        API + "/auth/login", method="POST",
        data=json.dumps({"usuario": usuario, "contrasena": contrasena}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=CONTEXTO) as r:
        return json.load(r)["token"]


PEDIDOS = [
    ("GET", "/imagenes", "leer"),
    ("GET", "/estadisticas", "leer"),
    ("POST", "/imagenes?nombre=prueba.tif", "escribir"),
    ("POST", f"/imagenes/{IMAGEN_INEXISTENTE}/analizar", "escribir"),
]

fallas = 0
print(f"API: {API}\n")
print(f"{'pedido':55} {'sin token':>9} {'lector':>7} {'colaborador':>11}")
tokens = {u: entrar(u, p) for u, p in CUENTAS.items()}
for metodo, ruta, tipo in PEDIDOS:
    sin = pedir(metodo, ruta)
    lec = pedir(metodo, ruta, tokens["lector"], {} if metodo == "POST" else None)
    col = pedir(metodo, ruta, tokens["santigodoy52"], {} if metodo == "POST" else None)
    print(f"{metodo + ' ' + ruta:55} {sin:>9} {lec:>7} {col:>11}")
    esperado_lector = 200 if tipo == "leer" else 403
    if sin != 401 or lec != esperado_lector or col in (401, 403):
        fallas += 1
        print("   ^ no es lo esperado")

print("\nOK: cada rol hace solo lo que le toca." if fallas == 0 else f"\n{fallas} pedido(s) fuera de lo esperado.")
sys.exit(1 if fallas else 0)
