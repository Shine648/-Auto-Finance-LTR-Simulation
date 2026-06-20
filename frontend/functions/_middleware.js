/**
 * Cloudflare Pages Function - API Proxy Middleware
 * 
 * Catches all /api/* and /simulate, /health, /macro-cycle requests
 * and proxies them to the local backend via cloudflared tunnel.
 * 
 * Set TUNNEL_URL in Pages environment variables:
 *   TUNNEL_URL = https://your-tunnel.trycloudflare.com
 */

const API_ROUTES = [
  '/health', '/macro-cycle', '/presets', '/simulate',
  '/simulate/', '/simulate/batch', '/simulate/presets',
  '/simulate/cycle', '/vasicek/', '/sensitivity/', '/cache/',
];

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const pathname = url.pathname;

  // Check if this is an API route
  const isApi = API_ROUTES.some(route => pathname.startsWith(route));
  if (!isApi) {
    // Not an API route — pass through to serve static files
    return context.next();
  }

  // Get tunnel URL from env (set in Pages dashboard)
  const tunnelUrl = (env.TUNNEL_URL || '').replace(/\/+$/, '');
  
  if (!tunnelUrl) {
    return new Response(JSON.stringify({ 
      error: 'TUNNEL_URL not configured',
      hint: 'Set TUNNEL_URL in Cloudflare Pages environment variables'
    }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }

  // Proxy to tunnel
  const targetUrl = `${tunnelUrl}${pathname}${url.search}`;
  
  try {
    const headers = new Headers(request.headers);
    // Remove hop-by-hop headers
    ['host', 'cf-connecting-ip', 'cf-ray', 'x-forwarded-proto', 'x-forwarded-for'].forEach(h => headers.delete(h));
    
    const proxyReq = new Request(targetUrl, {
      method: request.method,
      headers: headers,
      body: ['GET', 'HEAD'].includes(request.method) ? null : request.body,
    });

    const response = await fetch(proxyReq);
    
    // Create response with CORS headers
    const respHeaders = new Headers(response.headers);
    respHeaders.set('Access-Control-Allow-Origin', '*');
    respHeaders.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    respHeaders.set('Access-Control-Allow-Headers', 'Content-Type');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders,
    });
  } catch (err) {
    return new Response(JSON.stringify({ 
      error: 'Cannot reach backend', 
      detail: err.message,
      tunnel: tunnelUrl,
    }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
  }
}