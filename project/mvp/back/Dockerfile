FROM python:3.9-slim

# OpenCV necesita estas librerías del sistema; rasterio ya trae GDAL en su wheel
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Las dependencias van en su propia capa para no reinstalarlas con cada cambio de código.
# torch se instala primero desde el índice CPU: evita descargar varios GB de librerías CUDA.
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==2.8.0+cpu torchvision==0.23.0+cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# El contenedor corre con el usuario del host (ver docker-compose.yml), que no tiene home:
# Ultralytics y matplotlib necesitan una carpeta de configuración donde puedan escribir
ENV YOLO_CONFIG_DIR=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
