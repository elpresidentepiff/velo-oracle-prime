/**
 * VÉLØ Oracle - Production Cloudflare Worker
 * Global entrypoint with Railway backend routing
 * 
 * Architecture:
 * User → Cloudflare Worker (Edge) → Railway FastAPI → VÉLØ Engine
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
