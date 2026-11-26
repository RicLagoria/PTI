#!/usr/bin/env bash
# Prueba de tolerancia a fallos (Entrega 6 de PDC): con 3 réplicas de
# cliente-api, manda pedidos sin parar y a mitad de camino apaga una réplica
# de golpe (docker kill). Cuenta cuántos pedidos fallaron y a qué réplicas fue
# el tráfico antes y después.   Uso: bash despliegue/pdc/probar-failover.sh
set -euo pipefail
SALIDA="$(mktemp)"
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f compose.dev.yml -f compose.pdc.yml"
CERT=nginx/certs/agrovision.crt
bash pdc/escalar.sh 3 > /dev/null
TOKEN=$(curl -s --cacert "$CERT" -X POST -H "Content-Type: application/json" \
  -d '{"usuario":"lector","contrasena":"Lector2026!"}' https://localhost/api/auth/login \
  | python -c "import sys,json;print(json.load(sys.stdin)['token'])" | tr -d '\r')
VICTIMA=$($COMPOSE ps -q cliente-api | sed -n 2p)
pedir() {
  curl -s --cacert "$CERT" -o /dev/null -D - -H "Authorization: Bearer $TOKEN" https://localhost/api/imagenes \
    | tr -d '\r' | awk '/^HTTP/{c=$2} /^X-Atendido-Por/{sub(/^X-Atendido-Por: */, ""); gsub(/ /, ""); r=$0} END{print c, r}'
}
ok=0; mal=0
for i in $(seq 1 60); do
  if [ "$i" -eq 21 ]; then
    echo ">>> pedido 21: se apaga de golpe la réplica $(docker inspect -f '{{.Name}}' "$VICTIMA")"
    docker kill "$VICTIMA" > /dev/null
  fi
  read -r codigo replica <<< "$(pedir)"
  [ "$codigo" = "200" ] && ok=$((ok + 1)) || mal=$((mal + 1))
  echo "$i $codigo $replica"
done | tee "$SALIDA" | awk '/>>>/ || NR % 5 == 1'
ok=$(grep -c ' 200 ' "$SALIDA" || true); mal=$((60 - ok))
echo
echo "Réplicas que atendieron ANTES de la caída:";   sed -n '1,20p'  "$SALIDA" | awk '{print $3}' | sort | uniq -c
echo "Réplicas que atendieron DESPUÉS de la caída (\"a,b\" = probó a, falló, atendió b):"; sed -n '22,61p' "$SALIDA" | awk '{print $3}' | sort | uniq -c
echo
echo "Pedidos que pasaron por más de una réplica (el gateway probó la caída y reintentó en otra):"
grep -c ',' "$SALIDA" || true
echo
echo "Resultado: $ok de 60 pedidos OK, $mal con error."
echo "Levantando de nuevo la réplica caída..."
$COMPOSE up -d --no-deps --scale cliente-api=3 cliente-api > /dev/null 2>&1
