#!/usr/bin/env bash
# Backup de la base (PostgreSQL + PostGIS) con pg_dump en formato custom.
# Uso: bash despliegue/pdc/backup.sh      -> datos/backups/agrovision-AAAAMMDD-HHMMSS.dump
# Los ortomosaicos (datos/ortomosaicos) son archivos: se copian aparte.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p ../datos/backups
ARCHIVO="../datos/backups/agrovision-$(date +%Y%m%d-%H%M%S).dump"
docker compose -f compose.dev.yml exec -T db pg_dump -U agrovision -d agrovision -Fc > "$ARCHIVO"
echo "Backup: $ARCHIVO ($(du -h "$ARCHIVO" | cut -f1))"
