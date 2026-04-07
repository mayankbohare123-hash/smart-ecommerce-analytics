# ── Frontend Dockerfile ───────────────────────────────────────────────────────
# Stage 1: build the React app
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --silent

COPY . .

# Inject the backend API URL at build time.
# On Render/Railway, set VITE_API_URL to your backend's public URL.
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Stage 2: serve with Nginx ─────────────────────────────────────────────────
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Custom Nginx config — handle React Router (all paths → index.html)
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  index index.html; \
  location / { try_files $uri $uri/ /index.html; } \
  location /api { proxy_pass http://backend:8000; proxy_set_header Host $host; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
