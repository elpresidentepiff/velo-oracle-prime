/**
 * VÉLØ Oracle - Cloudflare Worker
 * Edge caching and rate limiting
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Add CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, x-api-key',
    };
    
    // Handle OPTIONS request
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }
    
    // Rate limiting
    const clientIP = request.headers.get('CF-Connecting-IP');
    const rateLimitKey = `rate_limit:${clientIP}`;
    
    const count = await env.RATE_LIMITER.get(rateLimitKey);
    if (count && parseInt(count) > 60) {
      return new Response('Rate limit exceeded', { 
        status: 429,
        headers: corsHeaders
      });
    }
    
    // Increment rate limit counter
    await env.RATE_LIMITER.put(rateLimitKey, (parseInt(count) || 0) + 1, {
      expirationTtl: 60
    });
    
    // Cache key
    const cacheKey = new Request(url.toString(), request);
    const cache = caches.default;
    
    // Check cache for GET requests
    if (request.method === 'GET') {
      let response = await cache.match(cacheKey);
      if (response) {
        return new Response(response.body, {
          ...response,
          headers: { ...response.headers, ...corsHeaders, 'X-Cache': 'HIT' }
        });
      }
    }
    
    // Forward to Railway backend
    const backendURL = env.RAILWAY_URL || 'https://velo-oracle.railway.app';
    const backendRequest = new Request(
      backendURL + url.pathname + url.search,
      {
        method: request.method,
        headers: request.headers,
        body: request.body
      }
    );
    
    const response = await fetch(backendRequest);
    
    // Cache successful GET responses
    if (request.method === 'GET' && response.status === 200) {
      const responseToCache = response.clone();
      await cache.put(cacheKey, responseToCache);
    }
    
    // Add CORS and cache headers
    const modifiedResponse = new Response(response.body, response);
    Object.keys(corsHeaders).forEach(key => {
      modifiedResponse.headers.set(key, corsHeaders[key]);
    });
    modifiedResponse.headers.set('X-Cache', 'MISS');
    
    return modifiedResponse;
  }
};
