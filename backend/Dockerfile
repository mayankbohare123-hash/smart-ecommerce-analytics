# ── Backend Dockerfile ────────────────────────────────────────────────────────
# Multi-stage build: keeps the final image lean by not including build tools.

# ── Stage 1: dependency install ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (needed for some scikit-learn wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create directories that need to exist at runtime
RUN mkdir -p uploads app/ml/models

# Run as non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Gunicorn for production — 2 workers per CPU core is a good starting point.
# For Render/Railway free tier (1 vCPU), 2 workers is appropriate.
CMD ["gunicorn", "app.main:app", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
