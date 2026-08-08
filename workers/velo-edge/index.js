/**
 * VÉLØ Oracle Edge Worker — v2.0 (hard-wired)
 * ============================================
 *
 * Real routing layer between Cloudflare edge and Railway FastAPI backend.
 * Every /velo/* route is wired to the correct Railway endpoint.
 * Includes: CORS, rate-limiting via KV, response caching, continuity state.
 *
 * Routes:
 *   GET  /velo/test          → health ping (no backend call)
 *   GET  /velo/status        → live system status from Railway /health
 *   GET  /velo/today         → today's verdicts from Railway /api/governed-card
 *   GET  /velo/verdicts      → raw verdicts from Railway /api/old-velo-verdicts
 *   GET  /velo/sigma         → sigma scorecard from Railway /api/canonical-scorecard
 *   GET  /velo/oracle        → full dashboard truth from Railway /api/dashboard-truth
 *   GET  /velo/continuity    → machine-readable session state for context pickup
 *   POST /velo/predict       → prediction engine at Railway /api/v1/predict/quick
 *   POST /velo/trigger/score → trigger daily scoring at Railway /api/trigger/score-daily
 *   POST /velo/trigger/sigma → trigger sigma reconciliation at Railway /api/trigger/sigma
 *   *    /api/*              → transparent proxy to Railway (all other API routes)
 *   *    /health             → proxy to Railway /health
 *
 * Bindings required (wrangler.toml):
 *   RATE_LIMITER  — KV namespace for rate limiting (optional, skipped if absent)
 *
 * Env vars:
 *   RAILWAY_URL   — Railway backend base URL
 *
 * Author: VÉLØ Oracle Team
 * Version: 2.0.0 — hard-wired 2026-08-08
 */

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key, X-Trigger-Secret',
  'Access-Control-Max-Age': '86400',
};

const CACHE_TTL = {
  status:      30,
  today:       120,
  verdicts:    120,
  sigma:       300,
  oracle:      60,
  continuity:  60,
};

const RATE_LIMIT = 120;

function jsonResponse(data, status = 200, extra_headers = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS, ...extra_headers },
  });
}

async function checkRateLimit(env, ip) {
  if (!env.RATE_LIMITER) return false;
  const key = `rl:${ip}`;
  const raw = await env.RATE_LIMITER.get(key);
  const count = raw ? parseInt(raw) : 0;
  if (count >= RATE_LIMIT) return true;
  await env.RATE_LIMITER.put(key, String(count + 1), { expirationTtl: 60 });
  return false;
}

async function proxyToBackend(backendBase, path, request, cacheKey = null, ttl = 0) {
  const cache = caches.default;

  if (request.method === 'GET' && cacheKey && ttl > 0) {
    const cached = await cache.match(cacheKey);
    if (cached) {
      const resp = new Response(cached.body, cached);
      resp.headers.set('X-Cache', 'HIT');
      resp.headers.set('X-Edge-Location', 'cloudflare');
      Object.entries(CORS_HEADERS).forEach(([k, v]) => resp.headers.set(k, v));
      return resp;
    }
  }

  const targetUrl = `${backendBase}${path}`;
  const h = new Headers(request.headers);
  h.set('X-Forwarded-By', 'VELO-Edge-Worker/2.0');
  h.set('X-Edge-Location', 'cloudflare');

  const proxyReq = new Request(targetUrl, {
    method: request.method,
    headers: h,
    body: (request.method !== 'GET' && request.method !== 'HEAD') ? await request.arrayBuffer() : null,
  });

  let backendResp;
  try {
    backendResp = await fetch(proxyReq);
  } catch (err) {
    return jsonResponse({ error: 'Backend unreachable', detail: err.message }, 502);
  }

  const resp = new Response(backendResp.body, {
    status: backendResp.status,
    statusText: backendResp.statusText,
    headers: backendResp.headers,
  });
  Object.entries(CORS_HEADERS).forEach(([k, v]) => resp.headers.set(k, v));
  resp.headers.set('X-Cache', 'MISS');
  resp.headers.set('X-Edge-Location', 'cloudflare');
  resp.headers.set('X-Backend', backendBase);

  if (request.method === 'GET' && cacheKey && ttl > 0 && backendResp.status === 200) {
    const toCache = resp.clone();
    toCache.headers.set('Cache-Control', `max-age=${ttl}`);
    await cache.put(cacheKey, toCache);
  }

  return resp;
}

export default {
  async fetch(request, env, ctx) {
    const backendBase = env.RAILWAY_URL || 'https://velo-oracle-production.up.railway.app';
    const url = new URL(request.url);
    const pathname = url.pathname;
    const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
    const edgeLoc = request.cf?.colo || 'unknown';

    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // Rate limiting
    if (await checkRateLimit(env, ip)) {
      return jsonResponse({ error: 'Rate limit exceeded', limit: RATE_LIMIT, window: '60 seconds', retry_after: 60 }, 429);
    }

    // /velo/test — edge health ping (no backend call)
    if (pathname === '/velo/test') {
      return jsonResponse({ ok: true, message: 'VÉLØ Cloudflare Worker Online', version: '2.0.0', edge_location: edgeLoc, timestamp: Date.now() });
    }

    // /velo/status — live system status (hits Railway /health)
    if (pathname === '/velo/status') {
      try {
        const backendHealth = await fetch(`${backendBase}/health`, {
          headers: { 'User-Agent': 'VELO-Edge-Worker/2.0' },
          signal: AbortSignal.timeout(8000),
        });
        const data = await backendHealth.json().catch(() => ({}));
        return jsonResponse({
          status: backendHealth.ok ? 'online' : 'degraded',
          models_loaded: data.models_loaded ?? (data.status === 'healthy'),
          db_connected: data.db_connected ?? (data.db !== 'UNCONFIGURED' && data.db !== undefined),
          version: 'v2-cloudflare',
          edge_location: edgeLoc,
          backend_url: backendBase,
          backend_status: data.status || (backendHealth.ok ? 'healthy' : 'unhealthy'),
          backend_detail: data,
          timestamp: new Date().toISOString(),
        });
      } catch (err) {
        return jsonResponse({
          status: 'degraded', models_loaded: false, db_connected: false,
          version: 'v2-cloudflare', edge_location: edgeLoc,
          error: 'Backend unreachable', detail: err.message,
          timestamp: new Date().toISOString(),
        }, 503);
      }
    }

    // /velo/today — today's governed card
    if (pathname === '/velo/today') {
      const qs = url.searchParams.get('date') ? `?date=${url.searchParams.get('date')}` : '';
      return proxyToBackend(backendBase, `/api/governed-card${qs}`, request, `${url.origin}/velo/today${qs}`, CACHE_TTL.today);
    }

    // /velo/verdicts — raw velo verdicts
    if (pathname === '/velo/verdicts') {
      const qs = url.searchParams.get('date') ? `?date=${url.searchParams.get('date')}` : '';
      return proxyToBackend(backendBase, `/api/old-velo-verdicts${qs}`, request, `${url.origin}/velo/verdicts${qs}`, CACHE_TTL.verdicts);
    }

    // /velo/sigma — canonical sigma scorecard
    if (pathname === '/velo/sigma') {
      const qs = url.searchParams.get('date') ? `?date=${url.searchParams.get('date')}` : '';
      return proxyToBackend(backendBase, `/api/canonical-scorecard${qs}`, request, `${url.origin}/velo/sigma${qs}`, CACHE_TTL.sigma);
    }

    // /velo/oracle — full dashboard truth
    if (pathname === '/velo/oracle') {
      const qs = url.searchParams.get('date') ? `?date=${url.searchParams.get('date')}` : '';
      return proxyToBackend(backendBase, `/api/dashboard-truth${qs}`, request, `${url.origin}/velo/oracle${qs}`, CACHE_TTL.oracle);
    }

    // /velo/continuity — machine-readable session state for context pickup
    // Returns: scoring status, learning gate, shadow model progress, last sigma,
    // pipeline_runs, system flags — everything needed to resume a session cold.
    if (pathname === '/velo/continuity') {
      const qs = url.searchParams.get('date') ? `?date=${url.searchParams.get('date')}` : '';
      return proxyToBackend(backendBase, `/api/runtime-truth${qs}`, request, `${url.origin}/velo/continuity${qs}`, CACHE_TTL.continuity);
    }

    // /velo/predict — prediction engine
    if (pathname === '/velo/predict') {
      if (request.method !== 'POST') return jsonResponse({ error: 'POST only' }, 400);
      return proxyToBackend(backendBase, '/api/v1/predict/quick', request);
    }

    // /velo/trigger/score — trigger daily scoring
    if (pathname === '/velo/trigger/score') {
      if (request.method !== 'POST') return jsonResponse({ error: 'POST only' }, 400);
      return proxyToBackend(backendBase, '/api/trigger/score-daily', request);
    }

    // /velo/trigger/sigma — trigger sigma reconciliation
    if (pathname === '/velo/trigger/sigma') {
      if (request.method !== 'POST') return jsonResponse({ error: 'POST only' }, 400);
      return proxyToBackend(backendBase, '/api/trigger/sigma', request);
    }

    // /health — direct health proxy
    if (pathname === '/health') {
      return proxyToBackend(backendBase, '/health', request);
    }

    // /api/* or /dashboard — transparent proxy to Railway
    if (pathname.startsWith('/api/') || pathname.startsWith('/dashboard')) {
      return proxyToBackend(backendBase, pathname + url.search, request);
    }

    // / — worker info
    if (pathname === '/' || pathname === '') {
      return jsonResponse({
        service: 'VÉLØ Oracle Edge API',
        version: '2.0.0',
        status: 'operational',
        edge_location: edgeLoc,
        backend: backendBase,
        routes: {
          'GET /velo/test':           'Edge health ping (no backend call)',
          'GET /velo/status':         'Live system status — models, DB, backend health',
          'GET /velo/today':          "Today's governed card (verdicts + product routing)",
          'GET /velo/verdicts':       'Raw velo verdicts for a date (?date=YYYY-MM-DD)',
          'GET /velo/sigma':          'Canonical sigma scorecard (?date=YYYY-MM-DD)',
          'GET /velo/oracle':         'Full dashboard truth (?date=YYYY-MM-DD)',
          'GET /velo/continuity':     'Machine-readable session state for context pickup',
          'POST /velo/predict':       'Prediction engine (race_data JSON body)',
          'POST /velo/trigger/score': 'Trigger daily scoring pipeline',
          'POST /velo/trigger/sigma': 'Trigger sigma reconciliation',
          'GET /health':              'Backend health check proxy',
          'ANY /api/*':               'Transparent proxy to Railway backend',
        },
      });
    }

    // 404
    return jsonResponse({ error: 'Route not found', path: pathname }, 404);
  },
};
