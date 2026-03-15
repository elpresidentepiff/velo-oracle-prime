# Production Dockerfile for VÉLØ Ingestion Spine Worker
# Build context: workers/ingestion_spine/
# Deploy: railway up workers/ingestion_spine/ --service ingestion-spine

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# PYTHONPATH=/app so `ingestion_spine` package is importable via relative imports
ENV PYTHONPATH=/app
# Force unbuffered output so logs are visible in Railway even on crash
ENV PYTHONUNBUFFERED=1
# Enable faulthandler to log C-level crashes (segfaults, OOM kills)
ENV PYTHONFAULTHANDLER=1

WORKDIR /app/ingestion_spine

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python healthcheck.py

# Diagnostic startup script — prints checkpoints at each import step.
# Reveals exactly where the container crashes even on OOM/import errors.
CMD ["python", "-u", "start_server.py"]
