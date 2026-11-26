#!/usr/bin/env bash
# Cambia la cantidad de réplicas de cliente-api y reinicia el gateway para que
# nginx tome las IPs nuevas.   Uso: bash despliegue/pdc/escalar.sh 3
set -euo pipefail
N="${1:-1}"
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f compose.dev.yml -f compose.pdc.yml"
$COMPOSE up -d --no-deps --scale cliente-api="$N" cliente-api
echo "Esperando que las $N réplicas estén sanas..."
for _ in $(seq 1 30); do
  sanas=$($COMPOSE ps cliente-api --format '{{.Health}}' | grep -c '^healthy$' || true)
  [ "$sanas" -ge "$N" ] && break
  sleep 2
done
$COMPOSE restart gateway
$COMPOSE ps cliente-api --format 'table {{.Name}}\t{{.Status}}'
