# VÉLØ Oracle - Railway + Cloudflare Integration

## Architecture

```
User → Cloudflare Worker (Edge) → Railway FastAPI → VÉLØ Engine
       (Global Entrypoint)         (Compute Engine)   (Intelligence)
```

**Cloudflare:** Routing, edge caching, protection  
**Railway:** FastAPI backend, VÉLØ intelligence  
**Integration:** Clean handshake with preserved headers

---

## Prerequisites

- Railway account with project created
- Cloudflare account with domain configured
- GitHub repository connected to Railway
- Environment variables configured

---

## Step 1: Railway Backend Setup

### 1.1 Deploy to Railway

```bash
# Connect GitHub repository
railway link

# Deploy
railway up

# Get deployment URL
railway domain
```

**Expected URL:** `https://velo-oracle-production.up.railway.app`

### 1.2 Configure Environment Variables

In Railway dashboard → Variables:

```env
ENV=production
API_KEY=your_secure_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key_here
PORT=8000
```

### 1.3 Verify Railway Backend

```bash
# Test health endpoint
curl https://velo-oracle-production.up.railway.app/health

# Expected response:
{
  "status": "ok",
  "app": "VÉLØ Oracle",
  "version": "v1.0",
  "environment": "production",
  "timestamp": "2025-11-19T..."
}
```

**If this fails, nothing else matters. Fix Railway first.**

### 1.4 Run Verification Script

```bash
python3 scripts/deployment/verify_railway.py \
  --url https://velo-oracle-production.up.railway.app \
  --output logs/railway_verification.json
```

**Expected:** All tests pass, status = operational

---

## Step 2: Cloudflare Worker Setup

### 2.1 Create Worker

1. Go to Cloudflare Dashboard → Workers
2. Click "Create a Worker"
3. Name: `velo-worker`
4. Paste worker code (see below)

### 2.2 Worker Code (Production)

```javascript
/**
 * VÉLØ Oracle - Production Cloudflare Worker
 */
export default {
  async fetch(request, env) {
    // Railway backend URL
    const backend = env.RAILWAY_URL || "https://velo-oracle-production.up.railway.app";
    
    // Parse request URL
    const url = new URL(request.url);
    
    // Build backend URL
    const backendURL = new URL(url.pathname + url.search, backend);
    
    // Create proxied request with all headers preserved
    const proxy = new Request(backendURL.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
    
    // Forward to Railway
    const resp = await fetch(proxy);
    
    // Return response with original headers
    return new Response(resp.body, resp);
  }
};
```

### 2.3 Configure Worker Environment Variables

In Worker Settings → Variables:

```env
RAILWAY_URL=https://velo-oracle-production.up.railway.app
```

### 2.4 Deploy Worker

Click "Save and Deploy"

---

## Step 3: Domain and Route Configuration

### 3.1 Add Custom Domain

1. Cloudflare Dashboard → Workers → `velo-worker`
2. Triggers → Custom Domains → Add Custom Domain
3. Enter: `api.yourdomain.com` (or your preferred subdomain)
4. Wait for DNS propagation (~5 minutes)

### 3.2 Add Route

1. Cloudflare Dashboard → Workers → `velo-worker`
2. Triggers → Routes → Add Route
3. Route: `api.yourdomain.com/*`
4. Worker: `velo-worker`
5. Save

**This ensures:** `api.yourdomain.com/*` → Worker → Railway

---

## Step 4: CORS Configuration

### 4.1 Verify CORS in FastAPI

File: `app/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Critical:** Without this, POST requests will fail.

### 4.2 Test CORS

```bash
curl -X OPTIONS https://api.yourdomain.com/health \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

**Expected headers:**
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: *
Access-Control-Allow-Headers: *
```

---

## Step 5: Production Verification

### 5.1 Test Direct Railway

```bash
curl https://velo-oracle-production.up.railway.app/health
```

**Expected:**
```json
{"status": "ok", "app": "VÉLØ Oracle"}
```

### 5.2 Test Through Cloudflare

```bash
curl https://api.yourdomain.com/health
```

**Expected:** Same JSON as Railway

### 5.3 Test POST Request

```bash
curl -X POST https://api.yourdomain.com/api/v1/predict/quick \
  -H "Content-Type: application/json" \
  -H "x-api-key: your_api_key" \
  -d '{
    "race_id": "TEST_001",
    "runner_id": "R1",
    "features": {"speed": 0.75},
    "market_odds": 5.0
  }'
```

**Expected:** Prediction response or 403 (API key required)

### 5.4 Run Full Verification

```bash
python3 scripts/deployment/verify_cloudflare.py \
  --cloudflare-url https://api.yourdomain.com \
  --railway-url https://velo-oracle-production.up.railway.app \
  --output logs/cloudflare_verification.json
```

**Expected:** All tests pass

---

## Step 6: Security Lockdown (Optional)

### 6.1 Restrict Railway Access

**Option A:** Disable public access

1. Railway Dashboard → Settings → Networking
2. Disable "Public Networking"
3. Add Cloudflare IP ranges to allowlist

**Option B:** Use Railway Private Networking

1. Enable Railway Private Networking
2. Update Worker to use private URL

### 6.2 Cloudflare IP Ranges

Add these to Railway allowlist:

```
173.245.48.0/20
103.21.244.0/22
103.22.200.0/22
103.31.4.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
188.114.96.0/20
197.234.240.0/22
198.41.128.0/17
162.158.0.0/15
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
131.0.72.0/22
```

### 6.3 Enable WAF (Web Application Firewall)

1. Cloudflare Dashboard → Security → WAF
2. Enable "OWASP Core Ruleset"
3. Add custom rules for API protection

---

## Step 7: Monitoring and Alerts

### 7.1 Railway Health Checks

Railway automatically monitors `/health` endpoint.

**Configure:**
- Interval: 60 seconds
- Timeout: 10 seconds
- Failure threshold: 3

### 7.2 Cloudflare Analytics

1. Cloudflare Dashboard → Analytics → Workers
2. Monitor:
   - Requests per second
   - Error rate
   - Response time
   - Cache hit ratio

### 7.3 Set Up Alerts

**Railway:**
- Deployment failures
- Health check failures
- High CPU/memory usage

**Cloudflare:**
- Worker errors
- High latency
- Rate limit hits

---

## Integration Checklist

| Item | Status | Notes |
|------|--------|-------|
| Railway backend deployed | ⬜ | URL: `https://velo-oracle-production.up.railway.app` |
| Railway health check passing | ⬜ | `GET /health` returns 200 |
| Environment variables set | ⬜ | API_KEY, SUPABASE_URL, etc. |
| CORS enabled in FastAPI | ⬜ | CORSMiddleware configured |
| Cloudflare Worker created | ⬜ | Name: `velo-worker` |
| Worker code deployed | ⬜ | Production routing script |
| Worker environment variables | ⬜ | RAILWAY_URL set |
| Custom domain added | ⬜ | `api.yourdomain.com` |
| Route configured | ⬜ | `/*` → `velo-worker` |
| Direct Railway test | ⬜ | `curl` health check |
| Cloudflare routing test | ⬜ | Through custom domain |
| POST request test | ⬜ | API endpoint working |
| CORS headers verified | ⬜ | OPTIONS request working |
| Verification scripts run | ⬜ | Both scripts pass |
| Security lockdown (optional) | ⬜ | Railway access restricted |
| Monitoring configured | ⬜ | Health checks and alerts |

---

## Troubleshooting

### Railway Health Check Fails

**Symptoms:** `curl` to Railway URL fails or returns error

**Solutions:**
1. Check Railway logs: `railway logs`
2. Verify environment variables are set
3. Check Dockerfile and build process
4. Ensure port 8000 is exposed
5. Verify FastAPI app starts correctly

### Cloudflare Worker Not Routing

**Symptoms:** Cloudflare URL returns error or different response

**Solutions:**
1. Check Worker logs in Cloudflare Dashboard
2. Verify RAILWAY_URL environment variable
3. Test Worker code in Cloudflare editor
4. Check route configuration (`/*` pattern)
5. Verify custom domain DNS is propagated

### CORS Errors

**Symptoms:** Browser shows CORS error, OPTIONS request fails

**Solutions:**
1. Verify CORSMiddleware in FastAPI
2. Check `allow_origins=["*"]` is set
3. Test OPTIONS request directly
4. Check Cloudflare Worker preserves headers
5. Verify no conflicting CORS rules in Cloudflare

### POST Requests Fail

**Symptoms:** POST returns 405, 403, or 500

**Solutions:**
1. Verify API key is correct
2. Check Content-Type header is `application/json`
3. Test POST directly to Railway first
4. Verify Worker forwards POST method
5. Check FastAPI endpoint exists and accepts POST

### 403 Forbidden

**Symptoms:** All requests return 403

**Solutions:**
1. Check API_KEY environment variable matches
2. Verify `x-api-key` header is sent
3. Test without API key validation first
4. Check Cloudflare WAF rules
5. Verify no IP blocking in Railway

---

## Advanced Configuration

### Enable Edge Caching

Use `cloudflare_worker_advanced.js` for:
- 60-second cache for GET requests
- Rate limiting (60 req/min per IP)
- Cache headers (X-Cache: HIT/MISS)
- Automatic error handling

### Load Balancing

For high traffic:
1. Deploy multiple Railway instances
2. Use Cloudflare Load Balancer
3. Configure health checks
4. Set up failover

### Custom Error Pages

Create custom 404/500 pages:
1. Cloudflare Dashboard → Custom Pages
2. Upload HTML for error pages
3. Configure Worker to return custom errors

---

## Production Deployment Complete

Once all checklist items are ticked:

✅ Railway + Cloudflare = Unified production system  
✅ Globally cached, secure, edge-accelerated  
✅ VÉLØ-powered prediction engine  
✅ Ready for production traffic

---

## Support

**Railway Issues:** https://railway.app/help  
**Cloudflare Issues:** https://community.cloudflare.com  
**VÉLØ Oracle:** Check repository documentation

---

**Integration Status:** Complete when all tests pass and checklist is ticked.
