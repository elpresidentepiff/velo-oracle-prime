/**
 * VÉLØ Oracle - Advanced Cloudflare Worker
 * Edge caching, rate limiting, and security
 */

export default {
  async fetch(request, env, ctx) {
    // Railway backend URL
    const backend = env.RAILWAY_URL || "https://velo-oracle-production.up.railway.app";
    
    // Parse request
    const url = new URL(request.url);
    const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    
    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, x-api-key',
          'Access-Control-Max-Age': '86400',
        }
      });
    }
    
    // Rate limiting
    if (env.RATE_LIMITER) {
      const rateLimitKey = `rate_limit:${clientIP}`;
      const count = await env.RATE_LIMITER.get(rateLimitKey);
      
      if (count && parseInt(count) > 60) {
        return new Response(JSON.stringify({
          error: 'Rate limit exceeded',
          limit: 60,
          window: '60 seconds'
        }), {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'X-Rate-Limit': '60',
            'X-Rate-Limit-Remaining': '0'
          }
        });
      }
      
      // Increment counter
      const newCount = (parseInt(count) || 0) + 1;
      await env.RATE_LIMITER.put(rateLimitKey, newCount.toString(), {
        expirationTtl: 60
      });
    }
    
    // Build backend URL
    const backendURL = new URL(url.pathname + url.search, backend);
    
    // Cache key for GET requests
    const cacheKey = new Request(backendURL.toString(), {
      method: 'GET'
    });
    
    // Check cache for GET requests
    if (request.method === 'GET') {
      const cache = caches.default;
      let response = await cache.match(cacheKey);
      
      if (response) {
        // Cache hit
        const newHeaders = new Headers(response.headers);
        newHeaders.set('X-Cache', 'HIT');
        newHeaders.set('Access-Control-Allow-Origin', '*');
        
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: newHeaders
        });
      }
    }
    
    // Create proxied request
    const proxy = new Request(backendURL.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.body
    });
    
    // Forward to Railway
    let response;
    try {
      response = await fetch(proxy);
    } catch (error) {
      return new Response(JSON.stringify({
        error: 'Backend unavailable',
        message: error.message
      }), {
        status: 503,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }
    
    // Clone response for caching
    const responseToCache = response.clone();
    
    // Cache successful GET responses
    if (request.method === 'GET' && response.status === 200) {
      const cache = caches.default;
      
      // Cache for 60 seconds
      const cacheHeaders = new Headers(responseToCache.headers);
      cacheHeaders.set('Cache-Control', 'public, max-age=60');
      
      const cachedResponse = new Response(responseToCache.body, {
        status: responseToCache.status,
        statusText: responseToCache.statusText,
        headers: cacheHeaders
      });
      
      ctx.waitUntil(cache.put(cacheKey, cachedResponse));
    }
    
    // Add CORS and cache headers
    const newHeaders = new Headers(response.headers);
    newHeaders.set('Access-Control-Allow-Origin', '*');
    newHeaders.set('X-Cache', 'MISS');
    newHeaders.set('X-Served-By', 'Cloudflare-Worker');
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders
    });
  }
};
