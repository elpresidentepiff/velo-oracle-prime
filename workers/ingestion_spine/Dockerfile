# Production Dockerfile for VÉLØ Ingestion Spine Worker
# Optimized for Railway deployment with proper dependency caching

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Python packages
# gcc: Required for compiling some Python packages
# Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
# This layer will only rebuild if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir: Don't cache pip packages to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 8000 (Railway will override with PORT env var)
EXPOSE 8000

# Health check to ensure service is running
# Railway uses this to verify deployment success
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:' + __import__('os').getenv('PORT', '8000') + '/health')" || exit 1

# Start command using Railway's PORT environment variable
# Railway dynamically assigns PORT, so we must use $PORT
# Using shell form to properly expand PORT environment variable
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
