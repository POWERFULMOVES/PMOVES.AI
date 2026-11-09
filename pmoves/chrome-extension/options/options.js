// PMOVES.AI Options Page

// Imported, not re-declared. This file previously carried its OWN copy of the
// nine localhost URLs in the reset handler -- a third copy, after constants.js
// and manifest.json. Copies are how this extension ended up localhost-only in
// one place and configurable in another.
import { buildServices } from '../lib/constants.js';

const $ = (sel) => document.querySelector(sel);

const SERVICES = [
  'tensorzero', 'gpuOrchestrator', 'hirag',
  'pmovesYt', 'agentZero', 'fluteGateway', 'prometheus', 'gateway',
];

const FEATURES = [
  'autoProcess', 'showFloatingButton', 'showThumbnailButtons', 'showNotifications',
];

const HEALTH_PATHS = {
  tensorzero:      '/health',
  gpuOrchestrator: '/api/gpu/status',
  hirag:           '/',
  pmovesYt:        '/healthz',
  agentZero:       '/healthz',
  fluteGateway:    '/healthz',
  prometheus:      '/-/healthy',
  gateway:         '/',
};

// ─── Load Config ─────────────────────────────────

async function loadConfig() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: 'getConfig' }, (config) => {
      if (chrome.runtime.lastError || !config) {
        resolve(null);
        return;
      }
      // Populate service URLs
      SERVICES.forEach((svc) => {
        const el = $(`#url-${svc}`);
        if (el && config.services?.[svc]) el.value = config.services[svc];
      });

      // Reflect the host the endpoints actually point at, so the field is not
      // blank while nine URLs say otherwise. Derived, never stored separately:
      // a second source of truth for the host is how they drift apart.
      try {
        const host = new URL(config.services?.pmovesYt || '').hostname;
        if (host) $('#fleet-host').value = host;
      } catch { /* unset or malformed -- leave the placeholder showing */ }

      // Auth
      if (config.auth?.agentZeroToken) $('#auth-agentZeroToken').value = config.auth.agentZeroToken;
      if (config.auth?.fluteApiKey) $('#auth-fluteApiKey').value = config.auth.fluteApiKey;

      // Features
      FEATURES.forEach((feat) => {
        const el = $(`#feat-${feat}`);
        if (el && config.features?.[feat] != null) el.checked = config.features[feat];
      });
      if (config.features?.healthPollInterval) {
        $('#feat-healthPollInterval').value = config.features.healthPollInterval;
      }

      resolve(config);
    });
  });
}

// ─── Save Config ─────────────────────────────────

$('#save-btn').addEventListener('click', async () => {
  const config = {
    services: {},
    auth: {},
    features: {},
  };

  SERVICES.forEach((svc) => {
    const el = $(`#url-${svc}`);
    if (el?.value) config.services[svc] = el.value.replace(/\/+$/, '');
  });

  config.auth.agentZeroToken = $('#auth-agentZeroToken').value;
  config.auth.fluteApiKey = $('#auth-fluteApiKey').value;

  FEATURES.forEach((feat) => {
    config.features[feat] = $(`#feat-${feat}`).checked;
  });
  config.features.healthPollInterval = parseInt($('#feat-healthPollInterval').value, 10) || 30;

  chrome.runtime.sendMessage({ action: 'updateConfig', config }, () => {
    const status = $('#save-status');
    status.textContent = 'Saved!';
    status.style.color = '#4CAF50';
    setTimeout(() => { status.textContent = ''; }, 2000);
  });
});

// ─── Fleet host ──────────────────────────────────
//
// Rewrites every endpoint to one host, keeping each service's port. This is the
// difference between "an extension that talks to my laptop" and "a fleet
// client": localhost is not an address any other machine can use.
//
// It does NOT save on its own -- it fills the fields so you can see exactly what
// it did and press Save. A control that silently rewrote nine stored endpoints
// would be indistinguishable from a bug the first time it guessed wrong.

function setStatus(text, color) {
  const el = $('#save-status');
  el.textContent = text;
  el.style.color = color;
}

$('#apply-host-btn').addEventListener('click', () => {
  const raw = $('#fleet-host').value.trim();
  if (!raw) {
    setStatus('Enter a host first (e.g. pmoves-z890, or localhost).', '#F44336');
    return;
  }
  const built = buildServices(raw);
  SERVICES.forEach((svc) => {
    if (built[svc]) $(`#url-${svc}`).value = built[svc];
  });
  const host = new URL(built.pmovesYt).hostname;
  // A host the manifest cannot reach is the failure this whole change exists to
  // fix, so name it HERE rather than letting every Test button fail opaquely.
  const permitted = host === 'localhost' || host.endsWith('.ts.net') || !host.includes('.');
  setStatus(
    permitted
      ? `Endpoints pointed at ${host} — click Save, then Test.`
      : `${host} is not permitted by the manifest (localhost and *.ts.net only) — fetches will be blocked.`,
    permitted ? '#FF9800' : '#F44336',
  );
});

// ─── Reset ───────────────────────────────────────

$('#reset-btn').addEventListener('click', () => {
  const defaults = buildServices('localhost');
  SERVICES.forEach((svc) => {
    $(`#url-${svc}`).value = defaults[svc] || '';
  });
  $('#fleet-host').value = '';
  $('#auth-agentZeroToken').value = '';
  $('#auth-fluteApiKey').value = '';
  $('#feat-autoProcess').checked = false;
  $('#feat-showFloatingButton').checked = true;
  $('#feat-showThumbnailButtons').checked = true;
  $('#feat-showNotifications').checked = true;
  $('#feat-healthPollInterval').value = 30;
  $('#save-status').textContent = 'Reset to defaults (click Save to apply)';
  $('#save-status').style.color = '#FF9800';
});

// ─── Test Individual Service ─────────────────────

document.querySelectorAll('.test-btn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const svc = btn.dataset.service;
    const urlEl = $(`#url-${svc}`);
    const baseUrl = validateServiceUrl(urlEl?.value || '');
    if (!baseUrl) { btn.textContent = 'No URL'; return; }

    btn.textContent = '...';
    btn.disabled = true;

    try {
      const start = performance.now();
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(`${baseUrl}${HEALTH_PATHS[svc] || '/healthz'}`, {
        signal: controller.signal,
      });
      clearTimeout(timer);
      const latency = Math.round(performance.now() - start);
      btn.textContent = res.ok ? `OK ${latency}ms` : `${res.status}`;
      btn.style.background = res.ok ? '#4CAF50' : '#f44336';
    } catch (e) {
      btn.textContent = 'Fail';
      btn.style.background = '#f44336';
    }

    setTimeout(() => {
      btn.textContent = 'Test';
      btn.style.background = '';
      btn.disabled = false;
    }, 3000);
  });
});

// ─── Test All Services ───────────────────────────

$('#test-all-btn').addEventListener('click', async () => {
  const table = $('#diagnostics-table');
  const tbody = table.querySelector('tbody');
  table.style.display = 'table';
  tbody.innerHTML = '<tr><td colspan="4">Testing...</td></tr>';

  const results = [];

  await Promise.all(SERVICES.map(async (svc) => {
    const baseUrl = validateServiceUrl($(`#url-${svc}`)?.value || '');
    if (!baseUrl) { results.push({ svc, status: 'Invalid URL', latency: 0, detail: '' }); return; }
    const start = performance.now();
    let status, latency, detail;

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(`${baseUrl}${HEALTH_PATHS[svc] || '/healthz'}`, {
        signal: controller.signal,
      });
      clearTimeout(timer);
      latency = Math.round(performance.now() - start);
      status = res.ok ? 'OK' : `HTTP ${res.status}`;
      detail = res.ok ? '' : await res.text().catch(() => '');
    } catch (e) {
      latency = Math.round(performance.now() - start);
      status = 'Error';
      detail = e.message;
    }

    results.push({ svc, status, latency, detail });
  }));

  tbody.innerHTML = '';
  results.forEach(r => {
    const tr = document.createElement('tr');
    tr.className = r.status === 'OK' ? 'row-ok' : 'row-fail';
    const tdSvc = document.createElement('td');
    tdSvc.textContent = r.svc;
    const tdStatus = document.createElement('td');
    tdStatus.textContent = r.status;
    const tdLatency = document.createElement('td');
    tdLatency.textContent = `${r.latency}ms`;
    const tdDetail = document.createElement('td');
    tdDetail.textContent = (r.detail || '').substring(0, 80);
    tr.append(tdSvc, tdStatus, tdLatency, tdDetail);
    tbody.appendChild(tr);
  });
});

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

/** Validate a user-configured service URL — allow only http/https schemes. */
function validateServiceUrl(raw) {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href.replace(/\/+$/, '');
    }
  } catch { /* invalid URL */ }
  return null;
}

// ─── Agent Zero Diagnostics ─────────────────────

function msgBg(payload) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(payload, (response) => {
      if (chrome.runtime.lastError) resolve({ error: chrome.runtime.lastError.message });
      else resolve(response);
    });
  });
}

$('#diag-agent-health').addEventListener('click', async () => {
  const el = $('#diag-agent-result');
  el.style.display = 'block';
  el.textContent = 'Checking Agent Zero health...';
  const r = await msgBg({ action: 'agentZeroHealth' });
  el.textContent = JSON.stringify(r, null, 2);
});

$('#diag-mcp-commands').addEventListener('click', async () => {
  const el = $('#diag-agent-result');
  el.style.display = 'block';
  el.textContent = 'Loading MCP commands...';
  const r = await msgBg({ action: 'agentZeroListCommands' });
  el.textContent = JSON.stringify(r, null, 2);
});

// ─── CHIT Geometry Diagnostics ──────────────────

$('#diag-recent-shapes').addEventListener('click', async () => {
  const pre = $('#diag-chit-result');
  const shapesDiv = $('#diag-chit-shapes');
  pre.style.display = 'block';
  pre.textContent = 'Loading shapes...';
  const r = await msgBg({ action: 'chitRecentShapes', limit: 10 });
  if (r?.shapes?.length) {
    shapesDiv.style.display = 'block';
    shapesDiv.innerHTML = '';
    r.shapes.forEach(s => {
      const div = document.createElement('div');
      div.style.cssText = 'margin:4px 0;font-size:13px;';

      const label = document.createElement('strong');
      label.textContent = s.label || s.shape_id;
      div.appendChild(label);

      const time = document.createElement('span');
      time.style.cssText = 'color:#888;margin-left:8px;';
      time.textContent = s.created_at || '';
      div.appendChild(time);

      const link = document.createElement('a');
      const gatewayBase = $('#url-gateway')?.value || 'http://localhost:8085';
      const vizUrl = `${gatewayBase}/viz/shape/${encodeURIComponent(s.shape_id)}.svg`;
      // Validate URL via constructor to prevent XSS (CodeQL #194, #196)
      try {
        const parsed = new URL(vizUrl);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
          link.href = parsed.href;
        }
      } catch { /* invalid URL — skip href assignment */ }
      link.target = '_blank';
      link.style.cssText = 'margin-left:8px;color:#667eea;';
      link.textContent = 'View SVG';
      div.appendChild(link);

      shapesDiv.appendChild(div);
    });
    pre.textContent = JSON.stringify(r, null, 2);
  } else {
    shapesDiv.style.display = 'none';
    pre.textContent = JSON.stringify(r, null, 2);
  }
});

$('#diag-recent-events').addEventListener('click', async () => {
  const el = $('#diag-chit-result');
  el.style.display = 'block';
  el.textContent = 'Loading events...';
  const r = await msgBg({ action: 'chitRecentEvents', limit: 20 });
  el.textContent = JSON.stringify(r, null, 2);
});

// ─── Init ────────────────────────────────────────

loadConfig();
