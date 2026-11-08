// PMOVES.AI Chrome Extension - Default Configuration
export const VERSION = '1.0.0';

// Ports are the stable fact; the HOST is what changes when this extension stops
// being a same-machine client and becomes a FLEET client.
//
// WHY THIS IS SPLIT OUT: every service was hardcoded to `localhost`, which can
// only ever reach the machine the browser runs on. Pointing the extension at
// another node meant editing nine fields by hand -- and it still failed, because
// MV3 blocks any fetch to a host absent from `host_permissions`, and that list
// was localhost-only. The URL saved, the request died, and nothing said why.
//
// The fleet answer is Tailscale, not a public port: MagicDNS gives every node a
// name, tailnet device identity does the authn, and the per-service tokens in
// `auth` do the authz. Same boundary the MCP roster already uses via ${TS_Z890}.
//
// NO ADDRESSES HERE, DELIBERATELY. MagicDNS names only -- tailnet addresses are
// 100.64/10 CGNAT, are runtime-derived, and do not belong in a committed tree.
export const SERVICE_PORTS = {
  tensorzero:      3030,
  gpuOrchestrator: 8200,
  hirag:           8086,
  pmovesYt:        8077,
  agentZero:       8080,
  fluteGateway:    8055,
  botzGateway:     8054,
  prometheus:      9090,
  gateway:         8085,
};

/**
 * Build the full service map for one host.
 * @param {string} host bare host -- 'localhost', or a MagicDNS name such as
 *   'pmoves-z890' / 'pmoves-z890.<tailnet>.ts.net'. No scheme, no port.
 * @param {string} [scheme] 'http' (default) or 'https'.
 */
export function buildServices(host, scheme = 'http') {
  const clean = String(host || 'localhost').trim()
    .replace(/^[a-z]+:\/\//i, '')   // tolerate a pasted scheme
    .replace(/[:/].*$/, '');        // and a pasted port or path
  return Object.fromEntries(
    Object.entries(SERVICE_PORTS).map(([k, p]) => [k, `${scheme}://${clean}:${p}`]),
  );
}

export const DEFAULT_SERVICES = buildServices('localhost');

export const DEFAULT_CONFIG = {
  services: { ...DEFAULT_SERVICES },
  auth: {
    agentZeroToken: '',
    fluteApiKey: '',
  },
  features: {
    autoProcess: false,
    showFloatingButton: true,
    showThumbnailButtons: true,
    showNotifications: true,
    healthPollInterval: 30, // seconds
  },
};

export const HEALTH_ENDPOINTS = {
  tensorzero:      { path: '/health',        method: 'GET' },
  gpuOrchestrator: { path: '/api/gpu/status', method: 'GET' },
  hirag:           { path: '/',              method: 'GET' },
  pmovesYt:        { path: '/healthz',       method: 'GET' },
  agentZero:       { path: '/healthz',       method: 'GET' },
  fluteGateway:    { path: '/healthz',       method: 'GET' },
  botzGateway:     { path: '/healthz',       method: 'GET' },
  prometheus:      { path: '/-/healthy',     method: 'GET' },
  gateway:         { path: '/',              method: 'GET' },
};

// Badge colors for health status
export const BADGE_COLORS = {
  healthy:  '#4CAF50',
  degraded: '#FF9800',
  down:     '#F44336',
  unknown:  '#9E9E9E',
};
