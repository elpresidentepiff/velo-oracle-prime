# Production Dockerfile for VÉLØ Ingestion Spine Worker
# Build context: workers/ingestion_spine/ (use `railway up workers/ingestion_spine/`)
# Or from repo root with dockerfilePath=workers/ingestion_spine/Dockerfile

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Works whether build context is workers/ingestion_spine/ OR repo root
# When context = workers/ingestion_spine/, file is at ./requirements.txt
# When context = repo root, this path fails — use dockerfilePath setting instead
COPY requirements.txt ./ingestion_spine/

RUN pip install --no-cache-dir -r ./ingestion_spine/requirements.txt

COPY . ./ingestion_spine/

RUN chmod +x ./ingestion_spine/start.sh

# PYTHONPATH=/app so `ingestion_spine` package is importable
ENV PYTHONPATH=/app

WORKDIR /app/ingestion_spine

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python healthcheck.py

CMD ["./start.sh"]
