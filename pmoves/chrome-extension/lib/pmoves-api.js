// PMOVES.AI Chrome Extension - Shared API Client
// All service integrations in one module.

import { DEFAULT_SERVICES, HEALTH_ENDPOINTS } from './constants.js';

let _services = { ...DEFAULT_SERVICES, n8n: 'http://localhost:5678' };

/** Update service URLs (call after loading config from storage). */
export function setServiceUrls(urls) {
  _services = { ..._services, ...urls };
}

function url(service, path) {
  return `${_services[service]}${path}`;
}

async function request(service, path, opts = {}) {
  const controller = new AbortController();
  const timeout = opts.timeout ?? 8000;
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url(service, path), {
      ...opts,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...opts.headers },
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res;
  } finally {
    clearTimeout(timer);
  }
}

// ─── TensorZero ──────────────────────────────────

export const tensorZero = {
  async chat(model, messages) {
    return request('tensorzero', '/v1/chat/completions', {
      method: 'POST',
      body: JSON.stringify({ model, messages }),
    });
  },

  async embed(model, input) {
    return request('tensorzero', '/v1/embeddings', {
      method: 'POST',
      body: JSON.stringify({ model, input }),
    });
  },
};

// ─── GPU Orchestrator ────────────────────────────

export const gpu = {
  async status() {
    return request('gpuOrchestrator', '/api/gpu/status');
  },

  async metricsSummary() {
    return request('gpuOrchestrator', '/api/gpu/metrics/summary');
  },

  async models(opts = {}) {
    const qs = new URLSearchParams();
    if (opts.provider) qs.set('provider', opts.provider);
    if (opts.includeUnloaded) qs.set('include_unloaded', 'true');
    const q = qs.toString();
    return request('gpuOrchestrator', `/api/gpu/models${q ? '?' + q : ''}`);
  },

  async loadModel(modelId, provider, priority = 5) {
    return request('gpuOrchestrator', '/api/gpu/models/load', {
      method: 'POST',
      body: JSON.stringify({ model_id: modelId, provider, priority }),
    });
  },

  async unloadModel(provider, modelId, force = false) {
    const qs = force ? '?force=true' : '';
    return request('gpuOrchestrator', `/api/gpu/models/unload/${encodeURIComponent(provider)}/${encodeURIComponent(modelId)}${qs}`, {
      method: 'POST',
    });
  },

  async optimize() {
    return request('gpuOrchestrator', '/api/gpu/optimize', { method: 'POST' });
  },

  async queue() {
    return request('gpuOrchestrator', '/api/gpu/queue');
  },
};

// ─── Hi-RAG v2 ──────────────────────────────────

export const hirag = {
  async query(query, topK = 10, rerank = true, opts = {}) {
    return request('hirag', '/hirag/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        top_k: topK,
        rerank,
        alpha: opts.alpha ?? 0.7,
        graph_boost: opts.graphBoost ?? 0.15,
        entity_types: opts.entityTypes,
        namespace: opts.namespace ?? 'pmoves',
      }),
    });
  },
};

// ─── PMOVES.YT ──────────────────────────────────

export const yt = {
  async ingest(videoUrl) {
    return request('pmovesYt', '/yt/ingest', {
      method: 'POST',
      body: JSON.stringify({ url: videoUrl }),
    });
  },

  async health() {
    return request('pmovesYt', '/healthz');
  },
};

// ─── Agent Zero ─────────────────────────────────

export const agentZero = {
  // GET /healthz — standard health check
  async health() {
    return request('agentZero', '/healthz');
  },

  // GET /mcp/commands — list available MCP commands
  async listCommands(token) {
    return request('agentZero', '/mcp/commands', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },

  // POST /mcp/execute — execute a named MCP command
  async executeCommand(token, cmd, args = {}) {
    return request('agentZero', '/mcp/execute', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: JSON.stringify({ cmd, arguments: args }),
    });
  },

  // POST /tasks — submit a task to Agent Zero runtime (synchronous, waits for result)
  async submitTask(token, message, metadata = {}) {
    return request('agentZero', '/tasks', {
      method: 'POST',
      timeout: 120000,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: JSON.stringify({ message, metadata }),
    });
  },

  // GET /jobs/{contextId} — get job conversation logs
  async getJobLog(token, contextId, length = 100) {
    return request('agentZero', `/jobs/${encodeURIComponent(contextId)}?length=${length}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  },

  // POST /sessions — send a conversational message
  async sendMessage(token, message, contextId = null) {
    const body = { message };
    if (contextId) body.context_id = contextId;
    return request('agentZero', '/sessions', {
      method: 'POST',
      timeout: 120000,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: JSON.stringify(body),
    });
  },

  // POST /events/publish — publish NATS event
  async publishEvent(token, topic, payload) {
    return request('agentZero', '/events/publish', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: JSON.stringify({ topic, payload, source: 'chrome-extension' }),
    });
  },
};

// ─── Flute Gateway (TTS/STT) ────────────────────

export const flute = {
  async synthesize(apiKey, text, opts = {}) {
    return request('fluteGateway', '/v1/voice/synthesize', {
      method: 'POST',
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
      body: JSON.stringify({
        text,
        persona_id: opts.personaId,
        provider: opts.provider,
        voice: opts.voice,
        engine: opts.engine,
        output_format: opts.outputFormat ?? 'wav',
      }),
    });
  },

  async synthesizeAudio(apiKey, text, opts = {}) {
    const controller = new AbortController();
    const timeout = opts.timeout ?? 30000;
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(url('fluteGateway', '/v1/voice/synthesize/audio'), {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'X-API-Key': apiKey } : {}),
        },
        body: JSON.stringify({
          text,
          persona_id: opts.personaId,
          provider: opts.provider,
          voice: opts.voice,
          output_format: opts.outputFormat ?? 'wav',
        }),
      });
      if (!res.ok) throw new Error(`Flute ${res.status}: ${res.statusText}`);
      return res.arrayBuffer();
    } finally {
      clearTimeout(timer);
    }
  },

  async personas(apiKey) {
    return request('fluteGateway', '/v1/voice/personas', {
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
    });
  },

  async config() {
    return request('fluteGateway', '/v1/voice/config');
  },
};

// ─── Mesh Agent (via Prometheus) ─────────────────

export const mesh = {
  async status() {
    return request('prometheus', '/api/v1/query?query=up', { timeout: 5000 });
  },

  async meshAgentUp() {
    const qs = encodeURIComponent('up{job="mesh-agent"}');
    return request('prometheus', `/api/v1/query?query=${qs}`, { timeout: 5000 });
  },
};

// ─── CHIT / Geometry Bus (Gateway) ──────────────

export const chit = {
  async publishEvent(cgp) {
    return request('gateway', '/geometry/event', {
      method: 'POST',
      body: JSON.stringify({ type: 'geometry.cgp.v1', data: cgp }),
    });
  },

  async decodeText(constellationIds = [], perConstellation = 10, shapeId = null) {
    return request('gateway', '/geometry/decode/text', {
      method: 'POST',
      body: JSON.stringify({
        shape_id: shapeId,
        constellation_ids: constellationIds,
        per_constellation: perConstellation,
      }),
    });
  },

  async calibrationReport(cgp) {
    return request('gateway', '/geometry/calibration/report', {
      method: 'POST',
      body: JSON.stringify(cgp),
    });
  },

  async jumpPoint(pid) {
    return request('gateway', `/shape/point/${encodeURIComponent(pid)}/jump`);
  },

  async demoRun(youtubeUrl, opts = {}) {
    return request('gateway', '/workflow/demo_run', {
      method: 'POST',
      timeout: 60000,
      body: JSON.stringify({ youtube_url: youtubeUrl, ...opts }),
    });
  },

  async recentShapes(limit = 10) {
    return request('gateway', `/viz/recent?limit=${limit}`);
  },

  async constellationIndex(shapeId) {
    return request('gateway', `/viz/shape/${encodeURIComponent(shapeId)}/constellations`);
  },

  async recentEvents(limit = 20) {
    return request('gateway', `/events/recent?limit=${limit}`);
  },
};

export function shapeSvgUrl(shapeId) {
  return `${_services.gateway}/viz/shape/${encodeURIComponent(shapeId)}.svg`;
}

// ─── Creator Pipeline (n8n Webhooks) ──────────────

export const creator = {
  async webhook(type, payload = {}) {
    // Expected types: 'wan-to-cgp', 'qwen-to-cgp', 'vibevoice-to-cgp'
    return request('n8n', `/webhook/${type}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
};

// ─── Health Check All ────────────────────────────

export async function healthCheckAll() {
  const results = {};

  const checks = Object.entries(HEALTH_ENDPOINTS).map(async ([name, ep]) => {
    const start = performance.now();
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(url(name, ep.path), {
        method: ep.method,
        signal: controller.signal,
      });
      clearTimeout(timer);
      const latency = Math.round(performance.now() - start);
      results[name] = { ok: res.ok, status: res.status, latency };
    } catch (err) {
      const latency = Math.round(performance.now() - start);
      results[name] = { ok: false, status: 0, latency, error: err.message };
    }
  });

  await Promise.allSettled(checks);
  return results;
}
