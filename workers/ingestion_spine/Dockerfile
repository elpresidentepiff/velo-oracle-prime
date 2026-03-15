# Production Dockerfile for VÉLØ Ingestion Spine Worker
# Build context: workers/ingestion_spine/
# Deploy: railway up workers/ingestion_spine/ --service ingestion-spine

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set PYTHONPATH so `ingestion_spine` is importable as a package from /app
ENV PYTHONPATH=/app

# Install dependencies (build context root = workers/ingestion_spine/)
WORKDIR /app/ingestion_spine
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

RUN chmod +x start.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python healthcheck.py

CMD ["/bin/bash", "start.sh"]
