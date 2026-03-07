// PMOVES.AI Options Page

const $ = (sel) => document.querySelector(sel);

const SERVICES = [
  'tensorzero', 'gpuOrchestrator', 'hirag',
  'pmovesYt', 'agentZero', 'fluteGateway', 'prometheus', 'gateway',
];

const FEATURES = [
  'autoProcess', 'showFloatingButton', 'showThumbnailButtons', 'showNotifications',
];

const HEALTH_PATHS = {
  tensorzero:      '/v1/models',
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

// ─── Reset ───────────────────────────────────────

$('#reset-btn').addEventListener('click', () => {
  SERVICES.forEach((svc) => {
    const defaults = {
      tensorzero: 'http://localhost:3030',
      gpuOrchestrator: 'http://localhost:8200',
      hirag: 'http://localhost:8086',
      pmovesYt: 'http://localhost:8077',
      agentZero: 'http://localhost:8080',
      fluteGateway: 'http://localhost:8055',
      prometheus: 'http://localhost:9090',
      gateway: 'http://localhost:8085',
    };
    $(`#url-${svc}`).value = defaults[svc] || '';
  });
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
    const baseUrl = urlEl?.value || '';
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
    const baseUrl = $(`#url-${svc}`)?.value || '';
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

  tbody.innerHTML = results.map(r => `
    <tr class="${r.status === 'OK' ? 'row-ok' : 'row-fail'}">
      <td>${r.svc}</td>
      <td>${r.status}</td>
      <td>${r.latency}ms</td>
      <td>${escapeHtml((r.detail || '').substring(0, 80))}</td>
    </tr>
  `).join('');
});

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
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
    shapesDiv.innerHTML = r.shapes.map(s => {
      const svgUrl = `${$('#url-gateway')?.value || 'http://localhost:8085'}/viz/shape/${encodeURIComponent(s.shape_id)}.svg`;
      return `<div style="margin:4px 0;font-size:13px;">
        <strong>${escapeHtml(s.label || s.shape_id)}</strong>
        <span style="color:#888;margin-left:8px;">${s.created_at || ''}</span>
        <a href="${svgUrl}" target="_blank" style="margin-left:8px;color:#667eea;">View SVG</a>
      </div>`;
    }).join('');
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
