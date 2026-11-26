#!/usr/bin/env bash
# Prueba de recuperación, sin tocar la base real:
#   1. cuenta filas de las tablas principales
#   2. hace un backup
#   3. lo restaura en una base aparte (agrovision_prueba)
#   4. compara las cuentas y mide cuánto tardó la restauración (RTO de la base)
set -euo pipefail
cd "$(dirname "$0")/.."
DC="docker compose -f compose.dev.yml exec -T db"
CONTAR="select 'usuarios', count(*) from usuarios union all select 'ortomosaicos', count(*) from ortomosaicos union all select 'analisis', count(*) from analisis union all select 'detecciones', count(*) from detecciones order by 1"
antes=$($DC psql -U agrovision -d agrovision -Atc "$CONTAR")
salida=$(bash pdc/backup.sh); echo "$salida"
archivo=$(echo "$salida" | sed -E 's/^Backup: (.*) \(.*$/\1/')
t0=$(date +%s)
bash pdc/restaurar.sh "$archivo" agrovision_prueba
t1=$(date +%s)
despues=$($DC psql -U agrovision -d agrovision_prueba -Atc "$CONTAR")
echo; echo "tabla|original|restaurada"
paste -d'|' <(echo "$antes") <(echo "$despues" | cut -d'|' -f2)
$DC psql -U agrovision -d postgres -qc "DROP DATABASE agrovision_prueba WITH (FORCE);"
echo
if [ "$antes" = "$despues" ]; then
  echo "OK: el backup se restauró completo en $((t1 - t0)) s."
else
  echo "FALLA: las cuentas no coinciden."; exit 1
fi
