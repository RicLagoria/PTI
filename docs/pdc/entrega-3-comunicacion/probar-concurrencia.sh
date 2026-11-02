#!/usr/bin/env bash
# Prueba de la Entrega 3 (caso P1): dos análisis simultáneos sobre la MISMA imagen.
# Resultado esperado: el primero corre (202), el segundo es rechazado (409), y
# detecciones.json termina completo y válido, sin mezclar resultados.
#
# Requisitos: entorno arriba (docker compose -f despliegue/compose.dev.yml up -d --build),
# un usuario creado con crear_usuarios.py, curl y python3.
#
# Uso:
#   USUARIO=RicLagoria CONTRASENA='...' IMAGEN=ruta/al/ortomosaico.tif \
#     bash docs/pdc/entrega-3-comunicacion/probar-concurrencia.sh
# Si IMAGEN no se define se usa la primera imagen ya subida (GET /imagenes).
set -u
API="${API:-http://localhost:8000}"
USUARIO="${USUARIO:?definí USUARIO}"
CONTRASENA="${CONTRASENA:?definí CONTRASENA}"

json() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
codigo() { curl -s -o /dev/null -w "%{http_code}" -X POST -H "Authorization: Bearer $TOKEN" "$1"; }

echo "== 0) Login"
TOKEN=$(curl -s -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"usuario\":\"$USUARIO\",\"contrasena\":\"$CONTRASENA\"}" | json 'd["token"]') \
  || { echo "No se pudo iniciar sesión"; exit 1; }
AUTH=(-H "Authorization: Bearer $TOKEN")

if [ -n "${IMAGEN:-}" ]; then
  echo "== 1) Subo $IMAGEN"
  ID=$(curl -s -X POST "${AUTH[@]}" --data-binary "@$IMAGEN" "$API/imagenes?nombre=$(basename "$IMAGEN")" | json 'd["id"]')
else
  echo "== 1) Uso la primera imagen ya subida"
  ID=$(curl -s "${AUTH[@]}" "$API/imagenes" | json 'd[0]["id"]')
fi
echo "imagen: $ID"

echo "== 2) Dos análisis a la vez sobre la misma imagen (cuadrante 1)"
URL="$API/imagenes/$ID/analisis?cuadrante=1&conf=0.10"
R1=$(mktemp); R2=$(mktemp)
curl -s -o "$R1" -w "%{http_code}" -X POST "${AUTH[@]}" "$URL" > "$R1.cod" &
curl -s -o "$R2" -w "%{http_code}" -X POST "${AUTH[@]}" "$URL" > "$R2.cod" &
wait
echo "pedido A -> $(cat "$R1.cod")   pedido B -> $(cat "$R2.cod")   (esperado: un 202 y un 409)"
echo "cuerpo del 409:"; cat "$R1" "$R2" | grep -i "en curso" | head -1

echo "== 3) Espero a que termine el análisis aceptado"
for _ in $(seq 1 600); do
  ESTADO=$(curl -s "${AUTH[@]}" "$API/imagenes/$ID/analisis" | json 'd["estado"]')
  echo "estado: $ESTADO"
  [ "$ESTADO" != "en_curso" ] && break
  sleep 2
done

echo "== 4) Con el lock libre, un análisis nuevo vuelve a aceptarse"
echo "pedido C -> $(codigo "$URL")   (esperado: 202)"

echo "== 5) Integridad de detecciones.json (se verifica dentro del contenedor)"
SERVICIO="${SERVICIO:-cliente-api}"
docker compose -f "$(dirname "$0")/../../../despliegue/compose.dev.yml" exec -T "$SERVICIO" python - "$ID" <<'PY'
import json, sys, glob
ruta = glob.glob(f"/datos/ortomosaicos/{sys.argv[1]}/detecciones.json")[0]
d = json.load(open(ruta))
print("JSON válido; bloques:", d["bloques_procesados"], "de", d["metadata"]["segmentos_totales"],
      "| detecciones:", len(d["detecciones"]))
PY
rm -f "$R1" "$R2" "$R1.cod" "$R2.cod"
