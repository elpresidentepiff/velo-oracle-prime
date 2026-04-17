# VÉLØ Oracle Edge API - Cloudflare Worker

Global edge proxy for VÉLØ Oracle FastAPI backend.

## Features

- **Global Edge Network**: Deploy to 300+ Cloudflare locations worldwide
- **Sub-100ms Latency**: Serve requests from the nearest edge location
- **CORS Handling**: Automatic CORS headers for all responses
- **Request Proxying**: Forward all requests to Railway backend
- **Health Monitoring**: Built-in health check endpoint

## Deployment

### Prerequisites

1. Install Wrangler CLI:
```bash
npm install -g wrangler
```

2. Login to Cloudflare:
```bash
wrangler login
```

### Deploy to Production

```bash
cd workers/velo-edge
wrangler deploy
```

### Deploy to Development

```bash
cd workers/velo-edge
wrangler deploy --env development
```

### Test Locally

```bash
cd workers/velo-edge
wrangler dev
```

## Endpoints

### Root
```
GET /
```
Returns worker information and available endpoints.

### Health Check
```
GET /health
```
Returns health status of both edge worker and backend API.

### Proxy Endpoints
All other endpoints are proxied to the Railway backend:

- `POST /v1/predict` - Generate race predictions
- `GET /v1/models` - Get model information
- `POST /v1/racecard` - Store race card
- `GET /v1/races/{race_id}` - Get race card
- `GET /v1/predictions/{race_id}` - Get predictions for race

## Configuration

Edit `wrangler.toml` to configure:

- `API_BASE`: Backend URL (Railway deployment)
- `name`: Worker name
- `compatibility_date`: Cloudflare Workers compatibility date

## Environment Variables

Set in `wrangler.toml`:

```toml
[vars]
API_BASE = "https://velo-oracle-production.up.railway.app"
```

Or via Cloudflare dashboard:
1. Go to Workers & Pages
2. Select your worker
3. Settings → Variables
4. Add `API_BASE` variable

## Monitoring

View logs:
```bash
wrangler tail
```

View analytics in Cloudflare dashboard:
1. Workers & Pages
2. Select worker
3. View metrics, requests, and errors

## Custom Domain

To use a custom domain:

1. Add domain in Cloudflare dashboard
2. Update `wrangler.toml`:
```toml
route = "api.velooracle.com/*"
zone_id = "your_zone_id"
```

3. Deploy:
```bash
wrangler deploy
```

## Rate Limiting (Future)

To add rate limiting, use Cloudflare Workers KV:

```javascript
// Check rate limit
const rateLimitKey = `rate_limit:${clientIP}`;
const requestCount = await env.RATE_LIMIT_KV.get(rateLimitKey);

if (requestCount && parseInt(requestCount) > 100) {
  return new Response('Rate limit exceeded', { status: 429 });
}

// Increment counter
await env.RATE_LIMIT_KV.put(rateLimitKey, (parseInt(requestCount || 0) + 1).toString(), {
  expirationTtl: 60 // 1 minute
});
```

## Caching (Future)

To add caching for GET requests:

```javascript
// Check cache
const cache = caches.default;
let response = await cache.match(request);

if (response) {
  return response;
}

// Fetch from backend
response = await fetch(backendRequest);

// Cache response
ctx.waitUntil(cache.put(request, response.clone()));

return response;
```
