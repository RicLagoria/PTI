#!/usr/bin/env bash
# Restaura un backup de backup.sh en una base.
# Uso: bash despliegue/pdc/restaurar.sh <archivo.dump> [base_destino]
#   base_destino por defecto: agrovision (la real; pide confirmación).
#   Para probar sin tocar nada, usar otra, p. ej. agrovision_prueba.
set -euo pipefail
cd "$(dirname "$0")/.."
ARCHIVO="$1"; DESTINO="${2:-agrovision}"
DC="docker compose -f compose.dev.yml exec -T db"
if [ "$DESTINO" = "agrovision" ]; then
  read -r -p "Esto reemplaza la base real 'agrovision'. Escribí SI para seguir: " ok
  [ "$ok" = "SI" ] || { echo "Cancelado."; exit 1; }
fi
$DC psql -U agrovision -d postgres -qc "DROP DATABASE IF EXISTS $DESTINO WITH (FORCE);"
$DC psql -U agrovision -d postgres -qc "CREATE DATABASE $DESTINO;"
$DC pg_restore -U agrovision -d "$DESTINO" --no-owner < "$ARCHIVO"
echo "Restaurado en '$DESTINO'."
