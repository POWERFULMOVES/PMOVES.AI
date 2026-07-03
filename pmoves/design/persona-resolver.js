// pmoves/design/persona-resolver.js — gateway-direct theme fetch.
// Deliberately calls GET /v1/agent/theme/{id} ONLY — no whoami, no Supabase (spec D2).

const DEFAULT_GW = "http://localhost:8054";

/** Build the theme URL (id-only, or the alter variant). */
export function agentThemeURL(id, { alter = null, gw = DEFAULT_GW } = {}) {
  const base = String(gw).replace(/\/+$/, "");
  const path = alter
    ? `/v1/agent/theme/${encodeURIComponent(id)}/alter/${encodeURIComponent(alter)}`
    : `/v1/agent/theme/${encodeURIComponent(id)}`;
  return base + path;
}

/**
 * Fetch a gateway theme object. `fetchImpl` is injectable for tests.
 * The default global fetch is bound to globalThis (bare refs throw "Illegal
 * invocation" under some sandboxed/proxied globals). A hung gateway is bounded
 * by opts.timeoutMs (default 8s) via AbortController so callers never hang.
 */
export async function fetchAgentTheme(id, opts = {}) {
  const fetchImpl =
    opts.fetchImpl || (typeof fetch !== "undefined" ? fetch.bind(globalThis) : null);
  if (!fetchImpl) throw new Error("no fetch available");
  const url = agentThemeURL(id, opts);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs ?? 8000);
  try {
    const res = await fetchImpl(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`theme ${id} -> HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}
