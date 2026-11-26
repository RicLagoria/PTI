"""
Arma los gráficos y la tabla de la prueba de escalado a partir de los
resumen-<N>rep-<V>vus.json que deja despliegue/pdc/medir-escalado.sh.

Uso: python docs/pdc/entrega-6-patrones/carga/graficar.py [carpeta]
      (por defecto, esta misma carpeta; p. ej. carga/corrida-1)
Salida: escalado.png y resultados.md dentro de esa carpeta.
"""
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CARPETA = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
SERIES = {1: ("1 réplica", "#2a78d6", "o"), 3: ("3 réplicas", "#eb6834", "s")}

datos = {}  # (replicas, vus) -> métricas
for f in CARPETA.glob("resumen-*rep-*vus.json"):
    n, v = map(int, re.match(r"resumen-(\d+)rep-(\d+)vus", f.stem).groups())
    m = json.loads(f.read_text(encoding="utf-8"))["metrics"]
    datos[(n, v)] = {
        "p95": m["http_req_duration"]["values"]["p(95)"] / 1000,
        "mediana": m["http_req_duration"]["values"]["med"] / 1000,
        "rps": m["http_reqs"]["values"]["rate"],
        "errores": m["http_req_failed"]["values"]["rate"] * 100,
        "pedidos": int(m["http_reqs"]["values"]["count"]),
    }

niveles = sorted({v for _, v in datos})
graficos = [("p95", "Latencia p95 (s)"), ("rps", "Throughput (pedidos/s)"), ("errores", "Errores (%)")]

plt.rcParams.update({"font.family": "Segoe UI", "font.size": 11})
fig, ejes = plt.subplots(1, 3, figsize=(13, 4.2))
for eje, (clave, titulo) in zip(ejes, graficos):
    for n, (nombre, color, marca) in SERIES.items():
        xs = [v for v in niveles if (n, v) in datos]
        ys = [datos[(n, v)][clave] for v in xs]
        eje.plot(xs, ys, color=color, linewidth=2, marker=marca, markersize=8,
                 markeredgecolor="white", markeredgewidth=2, label=nombre)
        if xs:
            eje.annotate(f"{ys[-1]:.1f}", (xs[-1], ys[-1]), textcoords="offset points",
                         xytext=(8, 4 if n == 3 else -12), color="#333", fontsize=10)
    eje.set_title(titulo, loc="left", fontsize=12, color="#1d1d1b")
    eje.set_xlabel("usuarios simultáneos", color="#555")
    eje.set_xticks(niveles)
    eje.set_ylim(bottom=0, top=max(1.0, eje.get_ylim()[1] * 1.12))
    eje.grid(axis="y", color="#e6e6e1", linewidth=1)
    for lado in ("top", "right"):
        eje.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eje.spines[lado].set_color("#bbb")
    eje.tick_params(colors="#555")
ejes[0].legend(frameon=False, loc="upper left")
fig.suptitle("cliente-api detrás del gateway: 1 vs 3 réplicas (k6, mismo escenario)", x=0.01, ha="left",
             fontsize=13, color="#1d1d1b")
fig.tight_layout()
fig.savefig(CARPETA / "escalado.png", dpi=150, facecolor="white")

filas = ["| Usuarios | Réplicas | p95 (s) | Mediana (s) | Throughput (ped/s) | Errores | Pedidos |",
         "|---|---|---|---|---|---|---|"]
for v in niveles:
    for n in SERIES:
        if (n, v) in datos:
            d = datos[(n, v)]
            filas.append(f"| {v} | {n} | {d['p95']:.2f} | {d['mediana']:.2f} | {d['rps']:.1f} | "
                         f"{d['errores']:.2f} % | {d['pedidos']} |")
(CARPETA / "resultados.md").write_text("\n".join(filas) + "\n", encoding="utf-8")
print("\n".join(filas))
