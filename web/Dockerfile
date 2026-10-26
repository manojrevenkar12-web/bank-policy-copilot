# syntax=docker/dockerfile:1.7
FROM node:22-slim AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY web .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY web/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /web/dist /usr/share/nginx/html
ENV API_UPSTREAM=http://api:8000
EXPOSE 8080
