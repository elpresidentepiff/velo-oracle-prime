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

# Make start script executable
RUN chmod +x start.sh

# Expose port 8000 (Railway will override with PORT env var)
EXPOSE 8000

# Health check to ensure service is running
# Railway uses this to verify deployment success
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python healthcheck.py

# Start command is defined in railway.json to properly use $PORT env var
