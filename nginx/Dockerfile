# FinFlow production entry image: reverse proxy + Vue static server.
#
# Stage 1 builds the Vue application; stage 2 serves the output with the
# hardened Nginx config (security headers, gzip, SPA fallback, /api proxy).
#
# Build context is the repository root (see docker-compose.yml):
#   docker build -f nginx/Dockerfile .

FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
