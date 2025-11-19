# VÉLØ Oracle - Production Deployment Guide

## Architecture

```
User → Cloudflare Worker → Railway (FastAPI) → Supabase
       (Edge Cache)         (Application)       (Database)
```

---

## Prerequisites

1. **Railway Account** - https://railway.app
2. **Cloudflare Account** - https://cloudflare.com
3. **Supabase Project** - https://supabase.com
4. **GitHub Repository** - Code pushed to `feature/v10-launch`

---

## Step 1: Supabase Setup

### Create Tables

```sql
-- Predictions table
CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    race_id TEXT NOT NULL,
    runner_id TEXT NOT NULL,
    probability FLOAT NOT NULL,
    edge FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    risk_band TEXT NOT NULL,
    market_odds FLOAT,
    actual_result TEXT
);

-- Backtests table
CREATE TABLE backtests (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    backtest_id TEXT NOT NULL,
    version TEXT NOT NULL,
    sample_size INTEGER NOT NULL,
    roi FLOAT NOT NULL,
    win_rate FLOAT NOT NULL,
    auc FLOAT NOT NULL,
    log_loss FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    metadata JSONB
);

-- Model metrics table
CREATE TABLE model_metrics (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    auc FLOAT NOT NULL,
    log_loss FLOAT NOT NULL,
    accuracy FLOAT,
    precision FLOAT,
    recall FLOAT,
    metadata JSONB
);

-- Drift alerts table
CREATE TABLE drift_alerts (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB
);

-- System health table
CREATE TABLE system_health (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    response_time_ms FLOAT,
    error_count INTEGER,
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_predictions_race ON predictions(race_id);
CREATE INDEX idx_predictions_timestamp ON predictions(timestamp DESC);
CREATE INDEX idx_backtests_timestamp ON backtests(timestamp DESC);
CREATE INDEX idx_model_metrics_model ON model_metrics(model_name, timestamp DESC);
CREATE INDEX idx_drift_alerts_timestamp ON drift_alerts(timestamp DESC);
CREATE INDEX idx_system_health_component ON system_health(component, timestamp DESC);
```

### Get Credentials

1. Go to Project Settings → API
2. Copy `Project URL` → `SUPABASE_URL`
3. Copy `anon public` key → `SUPABASE_KEY`

---

## Step 2: Railway Deployment

### Create New Project

1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Connect `elpresidentepiff/velo-oracle`
4. Select branch: `feature/v10-launch`

### Configure Environment Variables

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# API
API_KEY=your-secure-api-key-here

# Environment
ENV=production
DEBUG=false

# Models
MODELS_DIR=models

# Dataset
DATASET_PATH=storage/velo-datasets/racing_full_1_7m.parquet

# Monitoring
ENABLE_TELEMETRY=true
ENABLE_DRIFT_DETECTION=true

# Performance
MAX_CONCURRENT_PREDICTIONS=100
PREDICTION_TIMEOUT_SECONDS=5

# Caching
ENABLE_CACHE=true
CACHE_TTL_SECONDS=300

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=*

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
```

### Deploy

1. Railway will auto-deploy on push
2. Wait for build to complete (~5 minutes)
3. Get deployment URL: `https://your-app.railway.app`

### Upload Dataset

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# Upload dataset
railway run python scripts/convert_to_parquet_v2.py
```

### Upload Models

```bash
# Train models locally
python app/ml/trainers/train_all_v15_xgboost.py

# Upload to Railway
railway run mkdir -p models
railway run cp -r models/* models/
```

---

## Step 3: Cloudflare Setup

### Create Worker

1. Go to Workers & Pages → Create Worker
2. Name: `velo-oracle-edge`
3. Copy code from `deployment/cloudflare_worker.js`
4. Deploy

### Configure KV Namespace

1. Workers & Pages → KV
2. Create namespace: `RATE_LIMITER`
3. Bind to worker: `RATE_LIMITER`

### Set Environment Variables

```
RAILWAY_URL=https://your-app.railway.app
```

### Configure Custom Domain

1. Add domain: `api.velo-oracle.com`
2. Update DNS: CNAME → `velo-oracle-edge.workers.dev`
3. Enable SSL

---

## Step 4: Verify Deployment

### Health Check

```bash
curl https://api.velo-oracle.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "v1.0",
  "timestamp": "2025-11-19T10:00:00Z"
}
```

### Test Prediction

```bash
curl -X POST https://api.velo-oracle.com/api/v1/predict/quick \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-key" \
  -d '{
    "race_id": "TEST_001",
    "runner_id": "R1",
    "features": {"speed": 0.75, "rating": 95.0},
    "market_odds": 5.0
  }'
```

---

## Step 5: Monitoring

### Railway Logs

```bash
railway logs
```

### Supabase Dashboard

1. Go to Supabase → Table Editor
2. Check `predictions`, `model_metrics`, `system_health`

### Cloudflare Analytics

1. Go to Workers & Pages → Analytics
2. Monitor requests, errors, latency

---

## Step 6: Continuous Deployment

### Auto-Deploy on Push

Railway auto-deploys on push to `feature/v10-launch`.

### Manual Deploy

```bash
railway up
```

---

## Troubleshooting

### Build Fails

- Check `requirements_production.txt`
- Verify Python version (3.11)
- Check Railway logs

### Models Not Loading

- Verify models uploaded to Railway
- Check `MODELS_DIR` environment variable
- Verify file permissions

### Supabase Connection Fails

- Verify `SUPABASE_URL` and `SUPABASE_KEY`
- Check Supabase project status
- Verify network connectivity

### High Latency

- Enable Cloudflare caching
- Increase Railway workers
- Optimize model loading

---

## Production Checklist

- [ ] Supabase tables created
- [ ] Railway project deployed
- [ ] Environment variables configured
- [ ] Dataset uploaded
- [ ] Models trained and uploaded
- [ ] Cloudflare Worker deployed
- [ ] Custom domain configured
- [ ] Health check passing
- [ ] Test prediction successful
- [ ] Monitoring enabled
- [ ] Logs accessible
- [ ] Auto-deploy configured

---

## Support

For issues, contact: support@velo-oracle.com
