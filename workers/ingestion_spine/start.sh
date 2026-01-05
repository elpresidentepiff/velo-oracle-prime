#!/bin/bash
# Start script for Railway deployment
# Properly expands PORT environment variable

# Default to 8000 if PORT is not set
PORT=${PORT:-8000}

echo "Starting uvicorn on port $PORT"
exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
