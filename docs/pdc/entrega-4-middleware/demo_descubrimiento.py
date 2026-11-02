"""
Demostración del descubrimiento de servicios (Entrega 4 de PDC), sin Docker.

Levanta procesos reales: registro-servicios y varias instancias de
ia-inferencia (el mismo server.py que corre en el contenedor), y usa el
ClienteIA real de cliente-api para hablarles. Recorre seis escenarios:

  1. Alta automática: dos instancias se anuncian solas.
  2. Reparto: el cliente alterna entre ellas sin conocer ninguna URL.
  3. Caída abrupta (kill -9): el cliente pasa a la instancia sana sin error.
  4. Vencimiento: la instancia caída desaparece del registro al vencer su TTL.
  5. Instancia nueva y baja ordenada: aparece sola y la apagada se retira al instante.
  6. Registro caído: el cliente vuelve a la URL fija y sigue funcionando.

Uso, desde la raíz del repo y con las dependencias de los servicios instaladas:
    python docs/pdc/entrega-4-middleware/demo_descubrimiento.py
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import cv2
import httpx
import numpy as np

RAIZ = Path(__file__).resolve().parents[3]
SERVICIOS = RAIZ / "project" / "servicios"
PESOS = SERVICIOS / "ia-entrenamiento" / "semilla" / "train-3" / "weights" / "best.pt"
REGISTRO = "http://127.0.0.1:8103"
TTL_S = 6

procesos = {}


def lanzar(nombre, carpeta, puerto, extra_env=None):
    env = dict(os.environ, PYTHONUNBUFFERED="1", **(extra_env or {}))
    log = open(Path(os.environ.get("TMPDIR", "/tmp")) / f"demo-e4-{nombre}.log", "w")
    procesos[nombre] = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(puerto)],
        cwd=carpeta, env=env, stdout=log, stderr=subprocess.STDOUT,
    )


def esperar(url, segundos=120):
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    raise SystemExit(f"No respondió a tiempo: {url}")


def lanzar_ia(nombre, puerto):
    lanzar(nombre, SERVICIOS / "ia-inferencia" / "app", puerto, {
        "MODEL_PATH": str(PESOS), "REGISTRO_URL": REGISTRO, "REGISTRO_INTERVALO_S": "2",
        "PUERTO": str(puerto), "INSTANCIA_ID": nombre,
    })
    esperar(f"http://127.0.0.1:{puerto}/salud")
    time.sleep(0.5)


def registro():
    datos = httpx.get(f"{REGISTRO}/servicios/ia-inferencia", timeout=2).json()
    return [f"{i['id']} ({i['url']}, vence en {i['vence_en_s']} s)" for i in datos["instancias"]]


def titulo(texto):
    print(f"\n== {texto}")


def main():
    # El cliente se importa después de fijar sus variables: las lee al importarse.
    os.environ.update(REGISTRO_URL=REGISTRO, REGISTRO_CACHE_S="0",
                      IA_INFERENCIA_URL="http://127.0.0.1:8199")  # respaldo: todavía no hay nadie ahí
    sys.path.insert(0, str(SERVICIOS / "cliente-api" / "app"))
    from cliente_ia import ClienteIA

    _, jpeg = cv2.imencode(".jpg", np.full((640, 640, 3), 90, np.uint8))
    lote = [("tesela_demo", jpeg.tobytes())]

    def pedir(cliente, n=4):
        for _ in range(n):
            info = cliente.obtener_modelo()
            atendio_modelo = cliente.base_url
            dets = cliente.detectar_lote(lote, conf=0.10)
            print(f"   GET /modelo -> {atendio_modelo} (modelo {info.get('version')})"
                  f" | POST /detectar -> {cliente.base_url} ({len(dets)} detecciones)")

    titulo("0) Arranco registro-servicios (TTL de 6 s) y dos instancias de ia-inferencia: A y B")
    lanzar("registro", SERVICIOS / "registro-servicios" / "app", 8103, {"REGISTRO_TTL_S": str(TTL_S)})
    esperar(f"{REGISTRO}/salud")
    lanzar_ia("ia-a", 8101)
    lanzar_ia("ia-b", 8102)

    titulo("1) Alta automática: nadie las cargó a mano, se anunciaron solas")
    for linea in registro():
        print(f"   {linea}")

    titulo("2) Reparto: el cliente solo sabe el nombre 'ia-inferencia'")
    cliente = ClienteIA()
    pedir(cliente)

    titulo("3) Caída abrupta: kill -9 a A (no llega a darse de baja)")
    procesos["ia-a"].send_signal(signal.SIGKILL)
    procesos["ia-a"].wait()
    print("   el registro todavía la lista (su TTL no venció):")
    for linea in registro():
        print(f"   {linea}")
    pedir(cliente)

    titulo(f"4) Vencimiento: espero {TTL_S + 1} s sin latidos de A")
    time.sleep(TTL_S + 1)
    for linea in registro():
        print(f"   {linea}")

    titulo("5) Instancia nueva C (aparece sola) y apagado ordenado de B (se retira al instante)")
    lanzar_ia("ia-c", 8199)
    print("   con C arriba:")
    for linea in registro():
        print(f"   {linea}")
    procesos["ia-b"].send_signal(signal.SIGTERM)
    procesos["ia-b"].wait()
    print("   con B apagada con SIGTERM:")
    for linea in registro():
        print(f"   {linea}")
    pedir(cliente, 2)

    titulo("6) Registro caído: el cliente vuelve a IA_INFERENCIA_URL (que hoy es C) y sigue")
    procesos["registro"].send_signal(signal.SIGKILL)
    procesos["registro"].wait()
    pedir(cliente, 2)

    print("\nFIN: el consumidor nunca tuvo configurada la URL de A ni de B.")


if __name__ == "__main__":
    try:
        main()
    finally:
        for p in procesos.values():
            if p.poll() is None:
                p.terminate()
        for p in procesos.values():
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
