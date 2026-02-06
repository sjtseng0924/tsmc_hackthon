FROM node:lts-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:alpine
WORKDIR /srv
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
