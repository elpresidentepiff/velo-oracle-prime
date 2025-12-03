# VÉLØ Oracle v13 - Railway Deployment Guide

## ✅ Pre-Deployment Checklist

### 1. Pydantic v1.10.13 Configuration
- ✅ `requirements.txt` specifies `pydantic==1.10.13`
- ✅ `app/core/config.py` uses `from pydantic import BaseSettings`
- ✅ Local testing confirms Pydantic v1 compatibility
- ✅ Custom build script forces Pydantic v1 installation

### 2. Railway Configuration Files Created
- ✅ `railway_build.sh` - Custom build script with cache clearing
- ✅ `nixpacks.toml` - Railway build configuration
- ✅ `.railwayignore` - Excludes unnecessary files from deployment
- ✅ `Procfile` - Defines web process command

---

## 🚀 Deployment Steps

### Step 1: Push Changes to GitHub

```bash
cd /home/ubuntu/velo-oracle
git add railway_build.sh nixpacks.toml .railwayignore RAILWAY_DEPLOYMENT_GUIDE.md
git commit -m "feat: Add Railway deployment configuration with Pydantic v1.10.13 enforcement"
git push origin main
```

### Step 2: Configure Railway Environment Variables

Set these environment variables in your Railway project dashboard:

**Required Variables:**
```
SUPABASE_URL=https://ltbsxbvfsxtnharjvqcm.supabase.co
SUPABASE_KEY=<your_supabase_anon_key>
SUPABASE_SERVICE_ROLE_KEY=<your_supabase_service_role_key>
```

**Optional Variables (with defaults):**
```
API_ENV=production
API_VERSION=v1
LOG_LEVEL=INFO
LOG_JSON=true
MODEL_REGISTRY_PATH=ml/models/
ACTIVE_MODEL_NAME=SQPE
ACTIVE_MODEL_VERSION=v1_real
CORS_ORIGINS=*
```

### Step 3: Trigger Railway Deployment

**Option A: Via Railway Dashboard**
1. Go to your Railway project
2. Click "Deploy" or "Redeploy"
3. Railway will automatically detect `nixpacks.toml` and use the custom build process

**Option B: Via Railway CLI**
```bash
railway up
```

**Option C: Automatic (if GitHub integration is enabled)**
- Push to `main` branch triggers automatic deployment

### Step 4: Monitor Build Process

Watch for these key indicators in the Railway build logs:

```
✓ Clearing pip cache...
✓ Force-installing Pydantic v1.10.13...
✓ Pydantic version: 1.10.13
✓ Installing remaining dependencies...
✓ Final dependency verification:
  pydantic==1.10.13
✓ Build complete - Pydantic v1.10.13 confirmed
```

---

## 🔍 Post-Deployment Verification

### Step 1: Check Application Startup

Look for these log entries:
```
============================================================
VÉLØ Oracle API — Booting Prediction Engine
============================================================
Environment: production
Version: v1
Found X models in registry
Active model: SQPE-v1_real
============================================================
VÉLØ Oracle API Ready
============================================================
```

### Step 2: Test Health Endpoint

```bash
curl https://your-railway-app.railway.app/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-19T...",
  "version": "v1",
  "environment": "production"
}
```

### Step 3: Test Models Endpoint

```bash
curl https://your-railway-app.railway.app/v1/models
```

Expected response:
```json
{
  "models": [...],
  "active_model": {
    "name": "SQPE",
    "version": "v1_real",
    ...
  }
}
```

### Step 4: Test Predict Endpoint

```bash
curl -X POST https://your-railway-app.railway.app/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "race_id": "test_race",
    "runners": [...]
  }'
```

### Step 5: Verify Pydantic Version

Check the build logs or add a temporary endpoint to confirm:
```python
import pydantic
print(f"Runtime Pydantic version: {pydantic.VERSION}")
```

---

## 🛠️ Troubleshooting

### Issue: Pydantic v2 Still Being Installed

**Solution:**
1. Clear Railway build cache:
   - Railway Dashboard → Settings → Clear Build Cache
2. Redeploy the application
3. The `railway_build.sh` script will force-install Pydantic v1

### Issue: BaseSettings Import Error

**Symptom:**
```
ImportError: cannot import name 'BaseSettings' from 'pydantic'
```

**Solution:**
1. Verify `requirements.txt` has `pydantic==1.10.13` (not `>=` or `^`)
2. Check build logs to confirm Pydantic v1 was installed
3. Clear Railway cache and redeploy

### Issue: FastAPI Won't Boot

**Check:**
1. Environment variables are set correctly in Railway
2. Supabase credentials are valid
3. Application logs for specific error messages

---

## 📋 Build Script Details

### railway_build.sh

This script ensures Pydantic v1.10.13 is installed:

1. **Clears pip cache** - Removes any cached Pydantic v2 packages
2. **Upgrades pip** - Ensures latest pip version
3. **Force-installs Pydantic v1.10.13** - Uses `--force-reinstall` and `--no-cache-dir`
4. **Verifies installation** - Prints Pydantic version to build logs
5. **Installs remaining dependencies** - Installs all other requirements
6. **Final verification** - Runs `pip freeze | grep pydantic` to confirm

### nixpacks.toml

Configures Railway to:
- Use Python 3.11
- Run custom build script during install phase
- Start application with uvicorn

---

## 🔗 Integration Points

### Cloudflare Worker Proxy

After Railway deployment, update the Cloudflare Worker at:
```
https://velo-oracle-api.purorestrepo1981.workers.dev
```

Update `cloudflare/worker.js` to proxy requests to Railway:
```javascript
const RAILWAY_API_URL = 'https://your-railway-app.railway.app';

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const backendUrl = `${RAILWAY_API_URL}${url.pathname}${url.search}`;
    
    return fetch(backendUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
  }
}
```

### Supabase Database

Connected via environment variables:
- Project ID: `ltbsxbvfsxtnharjvqcm`
- Tables: models, races, runners, predictions, results, prediction_logs
- Views: v_race_card_with_predictions, v_model_leaderboard, v_backtest_summary, v_oracle_signals

---

## ✅ Success Criteria

Deployment is successful when:

1. ✅ Build logs show `Pydantic version: 1.10.13`
2. ✅ Application starts without import errors
3. ✅ `/v1/health` returns 200 OK
4. ✅ `/v1/models` returns model list
5. ✅ `/v1/predict` accepts and processes requests
6. ✅ No Pydantic v2 compatibility warnings in logs

---

## 📞 Support

If deployment issues persist:
1. Check Railway build logs for specific errors
2. Verify all environment variables are set
3. Test endpoints using the Railway-provided URL
4. Review Supabase connection status

---

**Deployment prepared by:** Manus AI  
**Date:** November 19, 2025  
**VÉLØ Oracle Version:** v13  
**Pydantic Version:** 1.10.13 (enforced)
