# Railway Deployment Configuration

This document describes the Railway deployment setup for the VÉLØ Ingestion Spine Worker.

## Files

### Dockerfile
- **Purpose**: Production-ready container image for Railway deployment
- **Base Image**: `python:3.11-slim`
- **Key Features**:
  - Optimized layer caching (requirements.txt copied first)
  - System dependencies (gcc) for Python package compilation
  - Health check on `/health` endpoint
  - Dynamic PORT handling via environment variable
  
### railway.json
- **Builder**: DOCKERFILE (uses the Dockerfile in this directory)
- **Restart Policy**: ON_FAILURE with 10 max retries
- **Start Command**: Defined in Dockerfile CMD

### .dockerignore
- **Purpose**: Exclude unnecessary files from Docker build context
- **Excluded**: Documentation, test files, git files, Python cache

## Railway Configuration

### Root Directory
Set to: `/workers/ingestion_spine`

### Environment Variables Required
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key (not anon key)
- `PORT` - Auto-provided by Railway (DO NOT SET MANUALLY)

### Build Process
1. Railway detects Dockerfile via railway.json
2. Docker builds image with optimized caching
3. Image size reduced by:
   - Using slim Python base
   - Removing apt cache after install
   - Using --no-cache-dir for pip
   - Excluding files via .dockerignore

### Deployment Verification
Once deployed, verify:
```bash
curl https://ingestion-spine-production.up.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "velo-ingestion-spine",
  "version": "1.0.0",
  "phase": "1"
}
```

## Local Testing

To test the Docker build locally:

```bash
cd /workers/ingestion_spine

# Build image
docker build -t ingestion-spine:local .

# Run container
docker run -p 8000:8000 \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_SERVICE_ROLE_KEY=your_key \
  ingestion-spine:local

# Test health endpoint
curl http://localhost:8000/health
```

## Troubleshooting

### Build Failures
- **Error**: `pip: command not found`
  - **Solution**: Using Dockerfile (not nixpacks) resolves this
  
- **Error**: Module import errors
  - **Solution**: Dockerfile copies all files, enabling relative imports

### Runtime Failures
- **Error**: Database connection failed
  - **Check**: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set
  
- **Error**: Port binding issues
  - **Check**: Railway's PORT variable is being used (automatic)

## Architecture Notes

### Relative Imports
The code uses relative imports:
```python
from .db import get_db_client, DatabaseClient
from .storage import get_storage_client, StorageClient
from .parsers import RacecardsParser, RunnersParser, FormParser
from .models import BatchStatus, FileType, ...
```

These work because:
1. All code is copied to `/app` in the container
2. Python module structure is preserved
3. uvicorn runs from the correct directory

### Module Structure
```
/app/
  ├── main.py (FastAPI app entry point)
  ├── db.py (Database client)
  ├── storage.py (Storage client)
  ├── parsers.py (CSV parsers)
  ├── models.py (Pydantic models)
  └── __init__.py (Package marker)
```
