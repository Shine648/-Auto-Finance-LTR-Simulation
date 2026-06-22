/**
 * Cloudflare Pages Function - API Proxy Middleware
 * 
 * Routes API requests to your local backend via cloudflared tunnel.
 * 
 * Configuration (pick one):
 *   1. Set TUNNEL_URL in Cloudflare Pages environment variables
 *   2. Use the Tunnel Config UI at /tunnel-config to generate _redirects
 * 
 * Static vs Dynamic routing:
 *   - Static: /health, /simulate, /macro-cycle, etc. → tunnel
 *   - Dynamic: /simulate/*, /sensitivity/*, etc. → tunnel (wildcard)
 *   - Everything else → Cloudflare Pages CDN (index.html)
 */

const API_ROUTES = [
  // Exact match routes
  '/health', '/macro-cycle', '/presets', '/simulate',
  // Wildcard prefix routes
  '/simulate/', '/simulate/batch', '/simulate/presets',
  '/simulate/cycle', '/simulate/heatmap',
  '/report/pdf',
  '/vasicek/', '/sensitivity/', '/cache/',
];

const STATIC_EXTENSIONS = [
  'html', 'css', 'js', 'json', 'png', 'jpg', 'jpeg',
  'gif', 'svg', 'ico', 'webp', 'woff', 'woff2', 'ttf',
  'eot', 'map', 'txt', 'xml',
];

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const pathname = url.pathname;

  // 1. Check if this is a static file request (serve from CDN)
  const parts = pathname.split('.');
  const ext = parts.length > 1 ? parts.pop().toLowerCase() : '';
  if (ext && STATIC_EXTENSIONS.includes(ext)) {
    return context.next();
  }

  // 2. Tunnel Config UI is served by Cloudflare Pages directly
  if (pathname === '/tunnel-config' || pathname === '/tunnel-config/') {
    // Uses the index.html SPA catch-all below
    return context.next();
  }

  // 3. Check if this is an API route that needs proxying
  const isApi = API_ROUTES.some(route => pathname.startsWith(route));
  if (!isApi) {
    // Not an API route → pass through to serve static files (SPA)
    return context.next();
  }

  // 4. Get tunnel URL from env (set in Pages dashboard) or from KV
  let tunnelUrl = (env.TUNNEL_URL || '').replace(/\/+$/, '');
  
  // Also check for tunnel URL from KV storage (set by config UI)
  if (!tunnelUrl && env.CF_TUNNEL_KV) {
    try {
      const stored = await env.CF_TUNNEL_KV.get('tunnel_url');
      if (stored) tunnelUrl = stored.replace(/\/+$/, '');
    } catch (e) {
      // KV not available, fall through
    }
  }
  
  if (!tunnelUrl) {
    return new Response(JSON.stringify({ 
      error: 'TUNNEL_URL not configured',
      hint: 'Set TUNNEL_URL in Cloudflare Pages environment variables, '
            + 'or use the Tunnel Config UI at /tunnel-config',
      docs: 'See CLOUDFLARE_DEPLOY.md for instructions'
    }), {
      status: 502,
      headers: { 
        'Content-Type': 'application/json', 
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-store'
      },
    });
  }

  // 5. Proxy the request to the tunnel
  const targetUrl = `${tunnelUrl}${pathname}${url.search}`;
  
  try {
    const headers = new Headers(request.headers);
    // Remove hop-by-hop headers that should not be forwarded
    const hopByHop = [
      'host', 'cf-connecting-ip', 'cf-ray', 
      'x-forwarded-proto', 'x-forwarded-for',
      'cf-visitor', 'cf-worker',
    ];
    hopByHop.forEach(h => headers.delete(h));
    
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
          'Access-Control-Max-Age': '86400',
        },
      });
    }
    
    const proxyReq = new Request(targetUrl, {
      method: request.method,
      headers: headers,
      body: ['GET', 'HEAD'].includes(request.method) ? null : request.body,
    });

    const response = await fetch(proxyReq);
    
    // Add CORS headers to response
    const respHeaders = new Headers(response.headers);
    respHeaders.set('Access-Control-Allow-Origin', '*');
    respHeaders.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    respHeaders.set('Access-Control-Allow-Headers', 'Content-Type');
    
    // Don't cache API responses
    respHeaders.set('Cache-Control', 'no-store, no-cache, must-revalidate');
    respHeaders.set('Pragma', 'no-cache');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: respHeaders,
    });
  } catch (err) {
    return new Response(JSON.stringify({ 
      error: 'Cannot reach backend via tunnel',
      detail: err.message,
      tunnel: tunnelUrl,
      hint: 'Make sure cloudflared is running on your server. '
            + 'Run: cloudflared tunnel --url http://localhost:8000'
    }), {
      status: 502,
      headers: { 
        'Content-Type': 'application/json', 
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-store'
      },
    });
  }
}