#!/usr/bin/env bash
# Prueba de la Entrega 2: los dos nodos (front+gateway y API) corren y se
# detienen de forma independiente.
# Uso (con el entorno ya levantado):  bash docs/pdc/entrega-2-infraestructura/probar-nodos.sh
set -u
cd "$(dirname "$0")/../../../project/mvp"

codigo() { curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$1"; }

esperar_api() {
  for _ in $(seq 1 60); do
    [ "$(codigo localhost:8080/api/imagenes)" = "200" ] && return 0
    sleep 1
  done
  return 1
}

echo "== 0) Estado inicial"
esperar_api || { echo "La API no responde: ¿corriste 'docker compose up -d'?"; exit 1; }
docker compose ps --format "{{.Service}}: {{.State}}"
echo "front /            -> $(codigo localhost:8080/)"
echo "front /api/imagenes -> $(codigo localhost:8080/api/imagenes)"

echo "== 1) Detengo SOLO la API: el front sigue sirviendo, /api devuelve 502"
docker compose stop back >/dev/null 2>&1
docker compose ps -a --format "{{.Service}}: {{.State}}"
echo "front /            -> $(codigo localhost:8080/)"
echo "front /api/imagenes -> $(codigo localhost:8080/api/imagenes)"

echo "== 2) Levanto la API sin tocar el front"
docker compose start back >/dev/null 2>&1
esperar_api && echo "front /api/imagenes -> 200 (la API volvió)"

echo "== 3) Detengo SOLO el front: la API sigue viva en la red interna"
docker compose stop front >/dev/null 2>&1
docker compose ps -a --format "{{.Service}}: {{.State}}"
echo "desde afuera :8080 -> $(codigo localhost:8080/) (000 = sin respuesta)"
echo -n "API por dentro      -> "
docker compose exec -T back python -c \
  "import urllib.request as u; print(u.urlopen('http://localhost:8000/imagenes').status)"

echo "== 4) Levanto el front de nuevo"
docker compose start front >/dev/null 2>&1
sleep 2
echo "front /            -> $(codigo localhost:8080/)"
esperar_api && echo "front /api/imagenes -> 200"
