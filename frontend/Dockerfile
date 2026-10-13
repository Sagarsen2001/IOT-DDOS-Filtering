# ============================================================
# Dockerfile — Frontend (Nginx)
# ============================================================
# Serves the static HTML/CSS/JS dashboard and reverse-proxies
# /api/ requests to the Flask backend container.
# ============================================================

FROM nginx:1.27-alpine

LABEL maintainer="IoT DDoS Filtering Project"
LABEL description="Nginx frontend serving IoT DDoS dashboard with API proxy"

# ── Custom Nginx configuration ────────────────────────────────
COPY nginx.conf /etc/nginx/conf.d/default.conf

# ── Static frontend assets ────────────────────────────────────
COPY . /usr/share/nginx/html/

# ── Remove non-web files from the web root ────────────────────
RUN rm -f /usr/share/nginx/html/Dockerfile \
          /usr/share/nginx/html/.dockerignore \
          /usr/share/nginx/html/nginx.conf \
          /usr/share/nginx/html/README.md

EXPOSE 80

# Nginx runs as PID 1 by default via the base image CMD

