#!/usr/bin/env bash
# Prueba de escalado horizontal (Entrega 6 de PDC): corre la misma carga (k6)
# con 10, 20 y 40 usuarios, primero contra 1 réplica de cliente-api y después
# contra 3, siempre detrás del gateway. Guarda un resumen por corrida y cómo
# repartió el balanceador en docs/pdc/entrega-6-patrones/carga/.
#   Uso: bash despliegue/pdc/medir-escalado.sh ["10 20 40"] [carpeta de salida]
set -euo pipefail
NIVELES="${1:-10 20 40}"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
CARGA="$RAIZ/docs/pdc/entrega-6-patrones/carga/${2:-corrida}"
mkdir -p "$CARGA"
cp "$RAIZ/docs/pdc/entrega-6-patrones/carga/prueba-carga.js" "$CARGA/"
COMPOSE="docker compose -f $RAIZ/despliegue/compose.dev.yml -f $RAIZ/despliegue/compose.pdc.yml"
for N in 1 3; do
  bash "$RAIZ/despliegue/pdc/escalar.sh" "$N"
  sleep 5
  for VUS in $NIVELES; do
    echo "=== $N réplica(s), $VUS usuarios ==="
    desde=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    # MSYS_NO_PATHCONV: que Git Bash en Windows no toque las rutas del contenedor.
    MSYS_NO_PATHCONV=1 docker run --rm --network despliegue_default \
      -v "$CARGA:/salida" -e VUS="$VUS" -e ETIQUETA="${N}rep-${VUS}vus" \
      grafana/k6:0.54.0 run --quiet /salida/prueba-carga.js || true
    $COMPOSE logs gateway --since "$desde" --no-log-prefix | grep -o 'replica=[0-9.:]*' | sort | uniq -c \
      > "$CARGA/reparto-${N}rep-${VUS}vus.txt" || true
  done
done
bash "$RAIZ/despliegue/pdc/escalar.sh" 1
echo "Resúmenes en $CARGA"
