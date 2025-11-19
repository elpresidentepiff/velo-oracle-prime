/**
 * VÉLØ Oracle Edge API - Cloudflare Worker
 * =========================================
 * 
 * Global edge proxy for VÉLØ Oracle FastAPI backend.
 * 
 * Features:
 * - Sub-100ms latency via Cloudflare edge network
 * - Request routing to Railway backend
 * - CORS handling
 * - Rate limiting (future)
 * - Caching (future)
 * 
 * Author: VÉLØ Oracle Team
 * Version: 1.0.0
 */

export default {
  async fetch(request, env, ctx) {
    // Get backend URL from environment
    const API_BASE = env.API_BASE || 'https://velo-oracle-production.up.railway.app';
    
    // Parse request URL
    const url = new URL(request.url);
    const pathname = url.pathname;
    const searchParams = url.searchParams;
    
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400',
    };
    
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: corsHeaders
      });
    }
    
    // Root endpoint - return worker info
    if (pathname === '/' || pathname === '') {
      return new Response(JSON.stringify({
        service: 'VÉLØ Oracle Edge API',
        version: '1.0.0',
        status: 'operational',
        edge_location: request.cf?.colo || 'unknown',
        backend: API_BASE,
        endpoints: {
          health: '/health',
          predict: '/v1/predict',
          models: '/v1/models',
          racecard: '/v1/racecard'
        }
      }), {
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders
        }
      });
    }
    
    // Health check endpoint
    if (pathname === '/health') {
      try {
        // Check backend health
        const backendHealth = await fetch(`${API_BASE}/health`, {
          method: 'GET',
          headers: {
            'User-Agent': 'VELO-Edge-Worker/1.0'
          }
        });
        
        const backendData = await backendHealth.json();
        
        return new Response(JSON.stringify({
          status: 'healthy',
          edge: {
            location: request.cf?.colo || 'unknown',
            country: request.cf?.country || 'unknown',
            timestamp: new Date().toISOString()
          },
          backend: {
            status: backendHealth.ok ? 'healthy' : 'unhealthy',
            ...backendData
          }
        }), {
          headers: {
            'Content-Type': 'application/json',
            ...corsHeaders
          }
        });
      } catch (error) {
        return new Response(JSON.stringify({
          status: 'degraded',
          error: 'Backend unreachable',
          message: error.message
        }), {
          status: 503,
          headers: {
            'Content-Type': 'application/json',
            ...corsHeaders
          }
        });
      }
    }
    
    // Proxy all other requests to backend
    try {
      // Build backend URL
      const backendUrl = `${API_BASE}${pathname}${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
      
      // Forward request to backend
      const backendRequest = new Request(backendUrl, {
        method: request.method,
        headers: request.headers,
        body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.arrayBuffer() : null
      });
      
      // Add custom headers
      backendRequest.headers.set('X-Forwarded-By', 'VELO-Edge-Worker');
      backendRequest.headers.set('X-Edge-Location', request.cf?.colo || 'unknown');
      
      // Fetch from backend
      const backendResponse = await fetch(backendRequest);
      
      // Clone response and add CORS headers
      const response = new Response(backendResponse.body, backendResponse);
      
      // Add CORS headers to response
      Object.entries(corsHeaders).forEach(([key, value]) => {
        response.headers.set(key, value);
      });
      
      // Add edge metadata
      response.headers.set('X-Edge-Location', request.cf?.colo || 'unknown');
      response.headers.set('X-Edge-Country', request.cf?.country || 'unknown');
      
      return response;
      
    } catch (error) {
      return new Response(JSON.stringify({
        error: 'Backend request failed',
        message: error.message,
        pathname: pathname
      }), {
        status: 502,
        headers: {
          'Content-Type': 'application/json',
          ...corsHeaders
        }
      });
    }
  }
};
