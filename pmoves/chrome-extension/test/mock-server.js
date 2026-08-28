// Mock server simulating all 9 PMOVES.AI services for Chrome extension validation.
// Usage: node mock-server.js
// Starts 9 HTTP servers on the same ports the extension expects.

const http = require('http');

const services = [
  {
    name: 'TensorZero',
    port: 3030,
    routes: {
      'GET /health': { status: 'ok' },
      'GET /healthz': 'ok',
      'POST /v1/chat/completions': (body) => ({
        choices: [{
          message: { role: 'assistant', content: `Mock TensorZero response to: ${body?.messages?.[0]?.content?.substring(0, 50) || '?'}` },
        }],
        usage: { prompt_tokens: 10, completion_tokens: 20 },
      }),
      'POST /v1/embeddings': { data: [{ embedding: new Array(384).fill(0.01) }] },
    },
  },
  {
    name: 'GPU Orchestrator',
    port: 8200,
    routes: {
      'GET /api/gpu/status': {
        vram_usage_percent: 42.5,
        temperature_c: 61,
        utilization_percent: 35,
        gpu_name: 'NVIDIA RTX 4090 (mock)',
        vram_total_mb: 24576,
        vram_used_mb: 10444,
      },
      'GET /api/gpu/metrics/summary': {
        vram_usage_percent: 42.5,
        utilization_percent: 35,
        temperature_c: 61,
      },
      'GET /api/gpu/models': { loaded_count: 3, models: ['llama3', 'whisper-small', 'yolov8'] },
      'POST /api/gpu/models/load': { status: 'loaded', model_id: 'test-model' },
      'POST /api/gpu/optimize': { message: 'VRAM optimized: freed 2.1 GB, 3 models remain loaded' },
      'GET /api/gpu/queue': { pending: 0, active: 1 },
      'GET /healthz': 'ok',
    },
  },
  {
    name: 'Hi-RAG v2',
    port: 8086,
    routes: {
      'GET /': { service: 'hi-rag-gateway', version: '2.1.0', status: 'healthy' },
      'GET /healthz': 'ok',
      'POST /hirag/query': (body) => ({
        results: [
          { text: `Mock result for "${body?.query}": PMOVES.AI uses a hybrid RAG architecture combining vector, graph, and full-text search for maximum recall.`, score: 0.923 },
          { text: 'The GPU orchestrator manages VRAM allocation across multiple model providers including Ollama and vLLM.', score: 0.871 },
          { text: 'Agent Zero coordinates task execution across the PMOVES service mesh using NATS JetStream.', score: 0.845 },
        ],
        query: body?.query,
        top_k: body?.top_k || 10,
      }),
    },
  },
  {
    name: 'PMOVES.YT',
    port: 8077,
    routes: {
      'GET /healthz': { status: 'ok', version: '1.4.0' },
      'POST /yt/ingest': (body) => ({
        status: 'queued',
        video_url: body?.url,
        job_id: 'mock-' + Date.now(),
        message: 'Video queued for ingestion',
      }),
    },
  },
  {
    name: 'Agent Zero',
    port: 8080,
    routes: {
      'GET /healthz': {
        status: 'ok', command: ['python', 'run_ui.py'], pid: 12345,
        nats: { url: 'nats://nats:4222', connected: true },
      },
      'GET /metrics': 'agent_zero_http_requests_total{} 42\n',
      'GET /config/environment': { port: 8080, nats_url: 'nats://nats:4222', agent_form: 'default' },
      'GET /mcp/commands': {
        default_form: 'default',
        commands: [
          { name: 'geometry.publish_cgp', description: 'Publish a CGP to geometry gateway' },
          { name: 'ingest.youtube', description: 'Ingest a YouTube URL' },
          { name: 'notebook.search', description: 'Search Open Notebook' },
          { name: 'e2b.sandbox.create', description: 'Create E2B sandbox' },
          { name: 'hirag.query', description: 'Query Hi-RAG knowledge base' },
          { name: 'supaserch.search', description: 'Deep research via SupaSerch' },
        ],
      },
      'POST /mcp/execute': (body) => ({
        cmd: body.cmd,
        result: { ok: true, detail: `Executed ${body.cmd}` },
      }),
      'POST /tasks': (body) => ({
        context_id: 'ctx-mock-' + Date.now(),
        response: `Mock analysis of: ${(body.message || '').substring(0, 100)}`,
        log: [{ role: 'agent', content: 'Mock task completed successfully.' }],
      }),
      'GET /jobs': {
        logs: [
          { role: 'user', content: 'Test' },
          { role: 'agent', content: 'Done' },
        ],
      },
      'POST /sessions': (body) => ({
        context_id: 'sess-' + Date.now(),
        response: `Mock response to: ${(body.message || '').substring(0, 80)}`,
      }),
      'POST /events/publish': { published: 'mock.topic.v1' },
      'GET /memory': { memories: [] },
    },
  },
  {
    name: 'Flute Gateway',
    port: 8055,
    routes: {
      'GET /healthz': { status: 'ok', service: 'flute-gateway', version: '1.2.0' },
      'POST /v1/voice/synthesize': (body) => ({
        duration_seconds: (body?.text?.length || 0) * 0.06,
        format: 'wav',
        sample_rate: 24000,
        text_length: body?.text?.length || 0,
        persona_id: body?.persona_id || 'default',
      }),
      'POST /v1/voice/synthesize/audio': 'RIFF_MOCK_AUDIO',
      'GET /v1/voice/personas': {
        personas: [
          { id: 'default', name: 'Nova', provider: 'vibevoice' },
          { id: 'warm', name: 'Aria', provider: 'kokoro' },
        ],
      },
      'GET /v1/voice/config': { providers: ['vibevoice', 'kokoro', 'f5tts'] },
    },
  },
  {
    name: 'Gateway (CHIT)',
    port: 8085,
    routes: {
      'GET /': '<html><body>PMOVES.AI Gateway</body></html>',
      'POST /geometry/event': { ok: true, shape_id: 'mock_shape_abc1', event: 'geometry.cgp.v1' },
      'POST /geometry/decode/text': (body) => ({
        items: [
          { constellation_id: body?.constellation_ids?.[0] || 'c1', text: 'Geometric projection of semantic anchor onto codebook vectors reveals latent conceptual alignment.', proj_est: 0.87, score: 0.923 },
          { constellation_id: body?.constellation_ids?.[0] || 'c1', text: 'Spectral weighting emphasizes high-density regions of the constellation radial distribution.', proj_est: 0.74, score: 0.871 },
          { constellation_id: body?.constellation_ids?.[0] || 'c1', text: 'Hierarchical super-node structure enables multi-scale geometric reasoning over knowledge graphs.', proj_est: 0.65, score: 0.812 },
        ],
      }),
      'POST /geometry/calibration/report': { KL: 0.0342, JS: 0.0087, coverage: 0.92, report: 'artifacts/reconstruction_report.md' },
      'GET /shape/point': { ok: true, locator: { modality: 'video', ref_id: 'dQw4w9WgXcQ', t: 42.5 } },
      'POST /workflow/demo_run': (body) => ({
        video: { video_id: 'mock123', title: 'Mock Video', segments_indexed: 6 },
        shape: {
          shape_id: 'shape-mock-' + Date.now(),
          constellations: ['c1', 'c2'],
          decode: { items: [{ text: 'Decoded geometric projection', score: 0.91 }] },
          calibration: { KL: 0.034, JS: 0.009, coverage: 0.91 },
        },
        hirag: { upsert: { count: 6 }, query: { results: [] } },
      }),
      'GET /viz/recent': { shapes: [{ shape_id: 'shape-abc1', label: 'Week 12 CGP', created_at: new Date().toISOString(), super_node_count: 3 }] },
      'GET /viz/shape': { constellations: [{ id: 'c1', summary: 'Primary cluster', point_count: 42 }] },
      'GET /events/recent': { events: [{ subject: 'geometry.cgp.v1', timestamp: new Date().toISOString() }, { subject: 'tokenism.cgp.ready.v1', timestamp: new Date().toISOString() }] },
    },
  },
  {
    name: 'BoTZ Gateway',
    port: 8054,
    routes: {
      'GET /healthz': { status: 'ok', service: 'botz-gateway', version: '0.5.0' },
      'GET /v1/agent/signatures': { signatures: 'loaded', count: 14 },
      'GET /v1/agent/theme/4090-claude': {
        agent_id: '4090-claude',
        display_name: '4090 Claude',
        glyph: '\u25c9',
        color: '#0D9488',
        accent: '#2DD4BF',
        voice: 'terse',
        resonance: ['cast-integration', 'voice-profiles', 'mobile-compute'],
        alters: [{
          name: '4090-field',
          glyph: '\u25ce',
          color: '#065F46',
          accent: '#10B981',
          voice: 'terse',
          resonance: ['polymorphic-ops', 'alter-discovery', 'pattern-mining'],
        }],
      },
      'GET /v1/agent/theme/4090-claude/alter/4090-field': {
        agent_id: '4090-claude',
        alter_name: '4090-field',
        glyph: '\u25ce',
        color: '#065F46',
        accent: '#10B981',
        voice: 'terse',
        resonance: ['polymorphic-ops', 'alter-discovery', 'pattern-mining', 'node-gateway', 'edge-deployment', 'frequency-tuning'],
        description: 'Polymorphic shape-shifter — single electron covering every spot.',
      },
    },
  },
  {
    name: 'Prometheus',
    port: 9090,
    routes: {
      'GET /-/healthy': 'Prometheus Server is Healthy.\n',
      'GET /api/v1/query': {
        status: 'success',
        data: {
          resultType: 'vector',
          result: [{ metric: { __name__: 'up', job: 'mesh-agent' }, value: [Date.now() / 1000, '1'] }],
        },
      },
    },
  },
];

let started = 0;

services.forEach(({ name, port, routes }) => {
  const server = http.createServer((req, res) => {
    // CORS headers (extension uses host_permissions, but just in case)
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    const key = `${req.method} ${req.url.split('?')[0]}`;
    // Also try with query string for Prometheus
    const keyWithQs = `${req.method} ${req.url}`;
    const handler = (Object.hasOwn(routes, key) && routes[key])
      || (Object.hasOwn(routes, keyWithQs) && routes[keyWithQs]);

    if (!handler) {
      // Try partial match for paths with dynamic segments (e.g. /jobs/:id)
      // Only match against the parsed pathname, not the full URL with query string
      let pathname;
      try { pathname = new URL(req.url, 'http://localhost').pathname; } catch { pathname = req.url.split('?')[0]; }

      const ALLOWED_METHODS = new Set(['GET', 'POST', 'PUT', 'DELETE', 'PATCH']);
      const match = ALLOWED_METHODS.has(req.method) && Object.keys(routes).find(k => {
        const spaceIdx = k.indexOf(' ');
        const m = k.substring(0, spaceIdx);
        const p = k.substring(spaceIdx + 1);
        return m === req.method && pathname.startsWith(p) && pathname.length < p.length + 64;
      });
      if (match) {
        respond(res, routes[match], req);
        return;
      }
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found', path: pathname }));
      return;
    }

    respond(res, handler, req);
  });

  function respond(res, handler, req) {
    if (typeof handler === 'function') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        let parsed = {};
        try { parsed = JSON.parse(body); } catch {}
        const result = handler(parsed);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(result));
      });
    } else if (typeof handler === 'string') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(handler);
    } else {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(handler));
    }
  }

  const bindHost = port === 8080 ? '0.0.0.0' : '127.0.0.1';
  server.listen(port, bindHost, () => {
    console.log(`  [OK] ${name.padEnd(20)} -> http://127.0.0.1:${port}`);
    started++;
    if (started === services.length) {
      console.log(`\n  All ${services.length} mock services running. Press Ctrl+C to stop.\n`);
    }
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`  [!!] ${name.padEnd(20)} -> port ${port} already in use (real service running?)`);
      started++;
    } else {
      console.error(`  [ERR] ${name}: ${err.message}`);
    }
  });
});

console.log('\nStarting PMOVES.AI mock services for Chrome extension validation...\n');
