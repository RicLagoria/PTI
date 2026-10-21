FROM python:3.9-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.8.0+cpu torchvision==0.23.0+cpu \
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

