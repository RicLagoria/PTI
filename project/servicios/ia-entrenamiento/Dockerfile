FROM python:3.9-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Variante de torch: "cpu" (por defecto) o una CUDA como "cu128". Las ruedas de
# CUDA se traen las librerías de NVIDIA y suman varios GB a la imagen, así que
# solo se construye así la imagen del worker que va a entrenar en GPU:
#   docker compose -f compose.ia.yml -f compose.ia.gpu.yml build
# Cada variante es un índice de PyPI aparte y el número de versión lleva la
# variante como sufijo local ("2.8.0+cu128"), que requirements.txt igual acepta.
ARG VARIANTE_TORCH=cpu

COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/${VARIANTE_TORCH} \
        torch==2.8.0+${VARIANTE_TORCH} torchvision==0.23.0+${VARIANTE_TORCH} \
    && pip install --no-cache-dir -r requirements.txt

COPY nucleo/ nucleo/
COPY api/ api/
COPY worker/ worker/
# Corrida train-3: se publica como primera versión si el registro arranca vacío
COPY semilla/ semilla/

ENV YOLO_CONFIG_DIR=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONUNBUFFERED=1

EXPOSE 8002
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8002"]

