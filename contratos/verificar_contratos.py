"""
Verifica que cada servicio en marcha cumple su contrato de contratos/ (Entrega 4 de PDC).

Para cada servicio pide su /openapi.json (lo genera FastAPI a partir del código
real) y lo compara con contratos/<servicio>.openapi.yaml, que es lo que leen
los demás equipos. Falla (código de salida 1) si:

  - la versión del código no es la del contrato;
  - el contrato promete una ruta/método que el código no tiene, o al revés;
  - un parámetro difiere (falta, sobra, o cambia si es obligatorio);
  - el código de éxito (2xx) del contrato no es el que devuelve el servicio.

No compara descripciones ni el detalle de los esquemas: el objetivo es atrapar
los cambios que rompen a un consumidor, no las diferencias de redacción.

Uso:
    python contratos/verificar_contratos.py \
        ia-inferencia=http://localhost:8001 \
        cliente-api=http://localhost:8000 \
        registro-servicios=http://localhost:8003
    python contratos/verificar_contratos.py --contratos-dir otra/carpeta ia-inferencia=...
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml

METODOS = {"get", "post", "put", "delete", "patch"}
IGNORAR_CODIGOS = {"422"}  # FastAPI lo agrega solo en toda ruta con parámetros


def _cargar_contrato(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _cargar_servicio(url: str) -> dict:
    with urllib.request.urlopen(f"{url.rstrip('/')}/openapi.json", timeout=10) as r:
        return json.load(r)


def _operaciones(doc: dict) -> Dict[Tuple[str, str], dict]:
    ops = {}
    for ruta, metodos in (doc.get("paths") or {}).items():
        for metodo, op in metodos.items():
            if metodo in METODOS:
                ops[(ruta, metodo)] = op
    return ops


def _parametros(op: dict) -> Dict[Tuple[str, str], bool]:
    """{(ubicación, nombre): obligatorio}"""
    return {
        (p.get("in"), p["name"]): bool(p.get("required", p.get("in") == "path"))
        for p in op.get("parameters", [])
        if "name" in p
    }


def _exitos(op: dict) -> Set[str]:
    return {c for c in (op.get("responses") or {}) if c.startswith("2")}


def comparar(nombre: str, contrato: dict, real: dict) -> List[str]:
    errores = []
    v_contrato = str(contrato.get("info", {}).get("version"))
    v_real = str(real.get("info", {}).get("version"))
    if v_contrato != v_real:
        errores.append(f"versión: contrato {v_contrato} ≠ código {v_real}")

    ops_c, ops_r = _operaciones(contrato), _operaciones(real)
    for ruta, metodo in sorted(set(ops_c) - set(ops_r)):
        errores.append(f"{metodo.upper()} {ruta}: está en el contrato pero el servicio no la tiene (rompe a quien la use)")
    for ruta, metodo in sorted(set(ops_r) - set(ops_c)):
        errores.append(f"{metodo.upper()} {ruta}: el servicio la expone pero el contrato no la documenta")

    for clave in sorted(set(ops_c) & set(ops_r)):
        etiqueta = f"{clave[1].upper()} {clave[0]}"
        pc, pr = _parametros(ops_c[clave]), _parametros(ops_r[clave])
        for ubic, param in sorted(set(pc) - set(pr)):
            errores.append(f"{etiqueta}: el parámetro {ubic}:{param} del contrato no existe en el servicio")
        for ubic, param in sorted(set(pr) - set(pc)):
            nivel = "obligatorio" if pr[(ubic, param)] else "opcional"
            errores.append(f"{etiqueta}: parámetro {nivel} {ubic}:{param} sin documentar")
        for p in sorted(set(pc) & set(pr)):
            if pc[p] != pr[p]:
                errores.append(f"{etiqueta}: {p[0]}:{p[1]} es obligatorio={pr[p]} en el servicio y obligatorio={pc[p]} en el contrato")
        ec, er = _exitos(ops_c[clave]) - IGNORAR_CODIGOS, _exitos(ops_r[clave]) - IGNORAR_CODIGOS
        if ec and er and not ec & er:
            errores.append(f"{etiqueta}: éxito {sorted(ec)} en el contrato y {sorted(er)} en el servicio")
    return errores


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    analizador.add_argument("servicios", nargs="+", metavar="nombre=url")
    analizador.add_argument("--contratos-dir", type=Path, default=Path(__file__).resolve().parent)
    args = analizador.parse_args()

    total = 0
    for par in args.servicios:
        nombre, _, url = par.partition("=")
        ruta = args.contratos_dir / f"{nombre}.openapi.yaml"
        try:
            errores = comparar(nombre, _cargar_contrato(ruta), _cargar_servicio(url))
        except Exception as e:
            errores = [f"no se pudo verificar: {e}"]
        n_ops = len(_operaciones(_cargar_contrato(ruta))) if ruta.is_file() else 0
        if errores:
            print(f"✗ {nombre} ({url}) contra {ruta.name}: {len(errores)} diferencia(s)")
            for e in errores:
                print(f"    - {e}")
        else:
            print(f"✓ {nombre} ({url}) cumple {ruta.name}: {n_ops} operaciones, versión y parámetros")
        total += len(errores)

    print(f"\n{'CONTRATOS OK' if total == 0 else f'{total} DIFERENCIA(S): el contrato y el código no coinciden'}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
