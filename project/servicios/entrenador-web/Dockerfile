FROM node:20-alpine AS build
WORKDIR /app

# Dependencias en su propia capa para no reinstalarlas con cada cambio de código
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
# Plantilla y no config final: el /auth se proxya a cliente-api, que puede estar
# en otra máquina. La imagen corre envsubst sobre /etc/nginx/templates/*.template
# al arrancar; el FILTER limita la sustitución a nuestra variable, porque si no
# envsubst también reemplazaría $uri y $host por vacío.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER=CLIENTE_API_URL \
    CLIENTE_API_URL=http://cliente-api:8000
COPY --from=build /app/dist /usr/share/nginx/html
