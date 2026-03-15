# Production Dockerfile for VÉLØ Ingestion Spine Worker
# Build context: workers/ingestion_spine/
# Deploy: railway up workers/ingestion_spine/ --service ingestion-spine

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# PYTHONPATH=/app so `ingestion_spine` package is importable via relative imports
ENV PYTHONPATH=/app

WORKDIR /app/ingestion_spine

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python healthcheck.py

# Use sh -c so Railway's PORT env var is expanded at runtime
CMD ["/bin/sh", "-c", "python -m uvicorn ingestion_spine.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --no-access-log"]
