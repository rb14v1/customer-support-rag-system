# syntax=docker/dockerfile:1
# Web component — React / Vite
# Build context: ./frontend  (docker build -f frontend/Dockerfile ./frontend)

# ---- Build stage: compile static assets ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first for better layer caching
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Copy source and build
COPY . .
RUN npm run build

# ---- Runtime stage: serve with nginx ----
FROM nginx:1.27-alpine AS runner

# Remove default nginx placeholder content
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Inject custom nginx config (SPA routing + non-privileged port 8080)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Allow the nginx worker process to read/write its required paths without root
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
