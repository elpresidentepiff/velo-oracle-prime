#!/bin/bash
# VÉLØ Ingestion Spine - Startup Script
# Properly handles Python module path for relative imports

set -e  # Exit on error

# Get PORT from Railway (defaults to 8000)
PORT=${PORT:-8000}

# Set PYTHONPATH to parent directory so relative imports work
# This allows Python to find the ingestion_spine package at /app/ingestion_spine/
export PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

echo "🚀 Starting VÉLØ Ingestion Spine..."
echo "   Port: $PORT"
echo "   PYTHONPATH: $PYTHONPATH"
echo "   Working Directory: $(pwd)"

# Run uvicorn with proper module path
# Use ingestion_spine.main:app so relative imports work
exec python -m uvicorn ingestion_spine.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --log-level info \
  --no-access-log
