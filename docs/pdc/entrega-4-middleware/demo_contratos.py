"""
Demostración de los contratos de interfaz (Entrega 4 de PDC), sin Docker.

1. Levanta los cuatro servicios con FastAPI (el mismo código que corre en los
   contenedores) y corre contratos/verificar_contratos.py contra todos.
2. Simula que alguien cambia una interfaz sin actualizar el contrato: copia
   contratos/ a una carpeta temporal, altera una copia y vuelve a verificar.
   El verificador tiene que fallar y señalar exactamente qué se rompió.

Uso, desde la raíz del repo y con las dependencias de los servicios instaladas:
    python docs/pdc/entrega-4-middleware/demo_contratos.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[3]
SERVICIOS = RAIZ / "project" / "servicios"
CONTRATOS = RAIZ / "contratos"
VERIFICADOR = CONTRATOS / "verificar_contratos.py"
TEMP = Path(tempfile.mkdtemp(prefix="demo-e4-contratos-"))

SERVICIOS_DEMO = {
    # nombre: (carpeta de server.py, puerto, variables)
    "registro-servicios": (SERVICIOS / "registro-servicios" / "app", 8203, {}),
    "ia-inferencia": (SERVICIOS / "ia-inferencia" / "app", 8201, {
        "MODEL_PATH": str(SERVICIOS / "ia-entrenamiento" / "semilla" / "train-3" / "weights" / "best.pt"),
    }),
    "ia-entrenamiento": (SERVICIOS / "ia-entrenamiento" / "api", 8202, {
        "MODELOS_DIR": str(TEMP / "modelos"), "DATASETS_DIR": str(TEMP / "datasets"),
        "TRABAJOS_DIR": str(TEMP / "trabajos"),
    }),
    "cliente-api": (SERVICIOS / "cliente-api" / "app", 8200, {
        "UPLOAD_DIR": str(TEMP / "ortomosaicos"),
        "DATABASE_URL": "postgresql://demo:demo@127.0.0.1:1/demo",  # el esquema no toca la base
    }),
}


def verificar(contratos_dir: Path) -> int:
    pares = [f"{n}=http://127.0.0.1:{p}" for n, (_, p, _) in SERVICIOS_DEMO.items()]
    return subprocess.run([sys.executable, str(VERIFICADOR), "--contratos-dir", str(contratos_dir), *pares]).returncode


def main():
    procesos = []
    try:
        print("== 0) Levanto los cuatro servicios")
        for nombre, (carpeta, puerto, extra) in SERVICIOS_DEMO.items():
            for v in extra.values():
                if "/demo-e4-contratos-" in v:
                    Path(v).mkdir(parents=True, exist_ok=True)
            log = open(TEMP / f"{nombre}.log", "w")
            procesos.append(subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(puerto)],
                cwd=carpeta, env=dict(os.environ, **extra), stdout=log, stderr=subprocess.STDOUT,
            ))
        for nombre, (_, puerto, _) in SERVICIOS_DEMO.items():
            for _ in range(240):
                try:
                    httpx.get(f"http://127.0.0.1:{puerto}/openapi.json", timeout=2).raise_for_status()
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                raise SystemExit(f"{nombre} no arrancó: ver {TEMP / (nombre + '.log')}")
            print(f"   {nombre} escuchando en :{puerto}")

        print("\n== 1) Verifico los cuatro servicios contra contratos/")
        codigo_ok = verificar(CONTRATOS)
        print(f"   código de salida: {codigo_ok}")

        print("\n== 2) Simulo cambios de interfaz sin acuerdo: otro integrante edita el contrato")
        print("   - ia-inferencia: el parámetro 'conf' de /detectar pasa a llamarse 'confianza'")
        print("   - cliente-api: se agrega una ruta que el servicio no implementa")
        print("   - registro-servicios: se sube la versión sin cambiar el código")
        alterados = TEMP / "contratos-alterados"
        shutil.copytree(CONTRATOS, alterados)
        p = alterados / "ia-inferencia.openapi.yaml"
        p.write_text(p.read_text(encoding="utf-8").replace("- name: conf\n", "- name: confianza\n", 1), encoding="utf-8")
        p = alterados / "cliente-api.openapi.yaml"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "paths:\n", "paths:\n  /imagenes/{imagen_id}/borrar:\n    post:\n      responses:\n        '200':\n          description: OK\n", 1),
            encoding="utf-8")
        p = alterados / "registro-servicios.openapi.yaml"
        p.write_text(p.read_text(encoding="utf-8").replace("version: 1.0.0", "version: 2.0.0", 1), encoding="utf-8")
        codigo_roto = verificar(alterados)
        print(f"   código de salida: {codigo_roto}")

        print(f"\nRESULTADO: contratos reales -> {codigo_ok} (0 = cumplen); "
              f"contratos alterados -> {codigo_roto} (1 = el verificador detectó la ruptura)")
        return 0 if (codigo_ok == 0 and codigo_roto == 1) else 1
    finally:
        for proc in procesos:
            proc.terminate()
        for proc in procesos:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(TEMP, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
