#!/usr/bin/env bash
# Genera el certificado autofirmado que usa el gateway (nginx/gateway.conf).
# Es para la demo: un servidor real usaría uno de Let's Encrypt.
# La clave privada queda en despliegue/nginx/certs/, que está en .gitignore.
set -euo pipefail
cd "$(dirname "$0")/../nginx"
mkdir -p certs
# MSYS_NO_PATHCONV evita que Git Bash en Windows convierta "/CN=..." en una ruta.
MSYS_NO_PATHCONV=1 openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout certs/agrovision.key -out certs/agrovision.crt \
  -subj "/CN=localhost/O=AgroVision PDC" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
echo "Listo: despliegue/nginx/certs/agrovision.{crt,key}"
