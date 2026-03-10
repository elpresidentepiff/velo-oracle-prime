# VÉLØ Oracle Phase 2 Deployment Guide

## Overview

This document outlines the complete Phase 2 infrastructure setup for VÉLØ Oracle, connecting:

- **Supabase** (Database)
- **Railway** (FastAPI Backend)
- **Cloudflare Workers** (Edge Proxy)
- **GitHub Actions** (CI/CD)

## Architecture

```
User Request
    ↓
Cloudflare Worker (Edge)
    ↓
Railway (FastAPI Backend)
    ↓
Supabase (PostgreSQL Database)
```

## 1. Supabase Configuration

### Database Connection

**URL:** `https://ltbsxbvfsxtnharjvqcm.supabase.co`

**Anon Key:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjM0ODgzNjksImV4cCI6MjA3OTA2NDM2OX0.iS1Sixo77BhZ2UQVwqVQcGOyBocSIy9ApABvsgLGmhY`

### Tables

- `models` - Model registry and performance logs
- `races` - Race card data
- `runners` - Runner information
- `predictions` - Prediction logs
- `results` - Race results
- `prediction_logs` - Detailed prediction logs

### Client Implementation

Location: `src/data/supabase_client.py`

Features:
- ✅ Connection health check
- ✅ Prediction logging
- ✅ Race card storage/retrieval
- ✅ Model performance tracking
- ✅ Prediction history queries

## 2. Railway Backend

### Current Status

- ✅ Deployed on Railway
- ✅ Pydantic v2 migration complete
- ✅ Branch: `feature/v10-launch`
- ✅ Auto-deploy enabled

### Environment Variables

Set these in Railway dashboard:

```bash
SUPABASE_URL=https://ltbsxbvfsxtnharjvqcm.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
ENABLE_PREDICTION_LOGGING=true
ENABLE_MODEL_REGISTRY=true
ENABLE_CACHE=true
```

### FastAPI Service

**Location:** `src/service/api_v2.py`

**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| GET | `/v1/health` | Legacy health check |
| POST | `/v1/predict` | Generate predictions |
| POST | `/v1/racecard` | Store race card |
| GET | `/v1/models` | Get models |
| POST | `/v1/models` | Store model log |
| GET | `/v1/races/{race_id}` | Get race card |
| GET | `/v1/predictions/{race_id}` | Get predictions |

### Deployment

Railway auto-deploys on push to `feature/v10-launch`.

Manual deployment:
```bash
git push origin feature/v10-launch
```

Or via Railway CLI:
```bash
railway up
```

## 3. Cloudflare Workers

### Worker Configuration

**Location:** `workers/velo-edge/`

**Files:**
- `index.js` - Worker code
- `wrangler.toml` - Configuration
- `README.md` - Documentation

### Deployment

#### Prerequisites

```bash
npm install -g wrangler
wrangler login
```

#### Deploy

```bash
cd workers/velo-edge
wrangler deploy
```

#### Update Existing Worker

If you already have a worker at `velo-oracle-api.purorestrepo1981.workers.dev`:

1. Go to Cloudflare Dashboard
2. Workers & Pages → velo-oracle-api
3. Edit code
4. Copy contents from `workers/velo-edge/index.js`
5. Save and deploy

#### Environment Variables

Set in Cloudflare dashboard or `wrangler.toml`:

```toml
[vars]
API_BASE = "https://velo-oracle-production.up.railway.app"
```

### Testing

```bash
# Test locally
wrangler dev

# Test deployed worker
curl https://velo-oracle-api.purorestrepo1981.workers.dev/health
```

## 4. GitHub Actions

### Workflow

**Location:** `.github/workflows/deploy.yml`

**Triggers:**
- Push to `feature/v10-launch`
- Push to `main`
- Pull requests

**Jobs:**
1. **Test** - Run linting and tests
2. **Deploy Railway** - Trigger Railway deployment
3. **Deploy Cloudflare** - Deploy Worker
4. **Notify** - Deployment summary

### Required Secrets

Set these in GitHub repository settings (Settings → Secrets and variables → Actions):

```
RAILWAY_TOKEN=your_railway_token
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
```

#### Get Railway Token

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Get token (displayed in browser)
```

Or get from Railway dashboard:
1. Account Settings → Tokens
2. Create new token
3. Copy token

#### Get Cloudflare API Token

1. Cloudflare Dashboard → My Profile → API Tokens
2. Create Token
3. Use "Edit Cloudflare Workers" template
4. Copy token

## 5. Environment Variables Sync

### Railway

**Option 1: Dashboard**
1. Railway Dashboard → velo-oracle → Variables
2. Add each variable manually

**Option 2: CLI Script**
```bash
./scripts/setup_railway_env.sh
```

**Option 3: Railway CLI**
```bash
railway variables set SUPABASE_URL="https://ltbsxbvfsxtnharjvqcm.supabase.co"
railway variables set SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Cloudflare

**Option 1: Dashboard**
1. Workers & Pages → velo-oracle-api → Settings → Variables
2. Add `API_BASE` variable

**Option 2: wrangler.toml**
```toml
[vars]
API_BASE = "https://velo-oracle-production.up.railway.app"
```

### GitHub Secrets

1. Repository → Settings → Secrets and variables → Actions
2. New repository secret
3. Add:
   - `RAILWAY_TOKEN`
   - `CLOUDFLARE_API_TOKEN`

## 6. Production Checks

### Health Check

```bash
# Check Railway backend
curl https://velo-oracle-production.up.railway.app/health

# Check Cloudflare Worker
curl https://velo-oracle-api.purorestrepo1981.workers.dev/health
```

### Prediction Flow Test

```bash
# Test prediction endpoint
curl -X POST https://velo-oracle-api.purorestrepo1981.workers.dev/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "test_001",
    "course": "Ascot",
    "date": "2025-11-19",
    "race_time": "14:30",
    "race_name": "Test Race",
    "dist": "1m",
    "going": "Good",
    "class": "1",
    "runners": [
      {
        "horse": "Test Horse",
        "trainer": "Test Trainer",
        "jockey": "Test Jockey",
        "age": 4,
        "weight": 9.0,
        "odds": 5.0
      }
    ]
  }'
```

### Supabase Write/Read Test

```bash
# Check if prediction was logged
# Query Supabase dashboard or use API:
curl https://velo-oracle-production.up.railway.app/v1/predictions/test_001
```

### Auto-Deploy Test

```bash
# Make a small change
echo "# Test commit" >> README.md

# Commit and push
git add README.md
git commit -m "test: trigger auto-deploy"
git push origin feature/v10-launch

# Check GitHub Actions
# Repository → Actions → VÉLØ Oracle Deploy
```

## 7. Monitoring

### Railway

1. Railway Dashboard → velo-oracle
2. Metrics tab
3. View:
   - CPU usage
   - Memory usage
   - Request count
   - Response times

### Cloudflare

1. Workers & Pages → velo-oracle-api
2. View:
   - Requests per second
   - Errors
   - CPU time
   - Edge locations

### Logs

**Railway:**
```bash
railway logs
```

**Cloudflare:**
```bash
wrangler tail
```

## 8. Troubleshooting

### Railway Not Deploying

1. Check GitHub integration: Railway → Settings → Source
2. Verify branch: Should be `feature/v10-launch`
3. Check logs: Railway → Deployments → View logs
4. Manual redeploy: Railway → Deployments → Redeploy

### Cloudflare Worker Not Responding

1. Check worker status: Cloudflare Dashboard → Workers
2. View logs: `wrangler tail`
3. Test locally: `wrangler dev`
4. Verify `API_BASE` variable is set

### Database Connection Failed

1. Check Supabase status: https://status.supabase.com/
2. Verify credentials in Railway variables
3. Test connection:
```bash
curl https://velo-oracle-production.up.railway.app/health
```

### GitHub Actions Failing

1. Check workflow runs: Repository → Actions
2. View logs for failed job
3. Verify secrets are set correctly
4. Check Railway/Cloudflare tokens are valid

## 9. Next Steps

After Phase 2 completion:

1. ✅ Load actual ML models into Railway
2. ✅ Implement real prediction logic
3. ✅ Add rate limiting to Cloudflare Worker
4. ✅ Set up monitoring and alerting
5. ✅ Configure custom domain
6. ✅ Add authentication/API keys
7. ✅ Implement caching strategy
8. ✅ Set up backup and disaster recovery

## 10. Support

For issues or questions:

1. Check logs first (Railway, Cloudflare, GitHub Actions)
2. Review this documentation
3. Check service status pages:
   - Railway: https://railway.app/status
   - Cloudflare: https://www.cloudflarestatus.com/
   - Supabase: https://status.supabase.com/

## Summary

**Phase 2 Status:**

- ✅ Supabase client implemented
- ✅ FastAPI v2 with database integration
- ✅ Cloudflare Worker code ready
- ✅ GitHub Actions workflow configured
- ✅ Environment variables documented
- ⚠️ Manual steps required:
  - Deploy Cloudflare Worker
  - Set Railway environment variables
  - Set GitHub secrets
  - Run production checks

**Estimated Time to Complete:** 30 minutes

**Priority:** Deploy Cloudflare Worker and set environment variables first, then run production checks.
