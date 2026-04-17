# Railway Deployment Guide - VÉLØ RP Parser

## Quick Deploy

1. **Create Railway Service**
   ```bash
   cd /home/ubuntu/velo-oracle-prime
   railway init
   railway up
   ```

2. **Set Environment Variables in Railway Dashboard**
   ```
   PARSER_SHARED_SECRET=<generate-random-long-string>
   LOG_LEVEL=INFO
   PORT=8000
   ```

3. **Deploy**
   - Railway will auto-detect the `railway.json` config
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Build will install dependencies from `requirements.txt`

4. **Get Public URL**
   - Copy the Railway public URL (e.g., `https://velo-rp-parser.up.railway.app`)

5. **Configure Ops Console**
   - Set `RAILWAY_API_URL` in Ops Console environment
   - Set `PARSER_SHARED_SECRET` (same value as Railway)

## API Endpoints

### Health Check
```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "velo-rp-parser"
}
```

### Parse Racing Post PDF
```bash
POST /parse/racingpost
Headers:
  X-VELO-SECRET: <PARSER_SHARED_SECRET>
  Content-Type: multipart/form-data

Body:
  file: <PDF file>
```

Response:
```json
{
  "day_key": "2026-01-05",
  "source": "racing_post",
  "races": [...],
  "runners": [...],
  "errors": [],
  "stats": {
    "races_inserted": 9,
    "runners_inserted": 69,
    "unmatched_runner_rows": 0
  }
}
```

## Testing Locally

```bash
cd /home/ubuntu/velo-oracle-prime/workers/ingestion_spine

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 8000

# Test health endpoint
curl http://localhost:8000/health

# Test parse endpoint
curl -X POST http://localhost:8000/parse/racingpost \
  -H "X-VELO-SECRET: test-secret" \
  -F "file=@/path/to/WOL_20260105_00_00_F_0012_XX_Wolverhampton.pdf"
```

## Troubleshooting

- **401 Unauthorized**: Check `X-VELO-SECRET` header matches `PARSER_SHARED_SECRET`
- **413 File Too Large**: PDF exceeds 50MB limit
- **500 Internal Error**: Check Railway logs for parser errors
