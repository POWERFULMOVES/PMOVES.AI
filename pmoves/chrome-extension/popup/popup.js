// PMOVES.AI Popup Dashboard

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ─── Health Grid ─────────────────────────────────

async function refreshHealth() {
  const health = await msg({ action: 'refreshHealth' });
  if (!health) return;

  $$('.health-item').forEach((el) => {
    const svc = el.dataset.service;
    const h = health[svc];
    const dot = el.querySelector('.health-dot');
    const lat = el.querySelector('.health-latency');

    dot.className = 'health-dot ' + (h ? (h.ok ? 'ok' : 'down') : 'unknown');
    lat.textContent = h?.latency ? `${h.latency}ms` : '';
  });
}

// ─── GPU Panel ───────────────────────────────────

async function refreshGpu() {
  try {
    const data = await msg({ action: 'getGpuStatus' });
    if (!data || data.error) return;

    const vramPct = data.vram_usage_percent ?? 0;
    $('#gpu-vram-bar').style.width = `${vramPct}%`;
    $('#gpu-vram-bar').style.background = vramPct > 90 ? '#f44336' : vramPct > 70 ? '#FF9800' : '#4CAF50';
    $('#gpu-vram-text').textContent = `${Math.round(vramPct)}%`;
    $('#gpu-temp').textContent = data.temperature_c != null ? `${data.temperature_c}C` : '--';
    $('#gpu-util').textContent = data.utilization_percent != null ? `${data.utilization_percent}%` : '--';

    const models = await msg({ action: 'getGpuModels' });
    $('#gpu-models').textContent = models?.loaded_count ?? '--';
  } catch {
    // GPU may not be available
  }
}

$('#gpu-optimize-btn').addEventListener('click', async () => {
  const btn = $('#gpu-optimize-btn');
  btn.disabled = true;
  btn.textContent = 'Optimizing...';
  try {
    const result = await msg({ action: 'gpuOptimize' });
    showResult(result?.message || 'Optimization complete');
    refreshGpu();
  } catch (e) {
    showResult('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Optimize VRAM';
  }
});

// ─── Quick Actions ───────────────────────────────

$('#ingest-btn').addEventListener('click', async () => {
  const url = $('#ingest-url').value.trim();
  if (!url) return;
  const r = await msg({ action: 'processVideo', url });
  showResult(r?.status === 'queued' ? 'Video queued for ingestion' : (r?.error || 'Sent'));
  $('#ingest-url').value = '';
});

$('#rag-btn').addEventListener('click', async () => {
  const query = $('#rag-query').value.trim();
  if (!query) return;
  showResult('Searching...');
  const r = await msg({ action: 'hiragQuery', query, topK: 5, rerank: true });
  if (r?.results?.length) {
    const text = r.results.map((res, i) =>
      `${i + 1}. [${(res.score || 0).toFixed(3)}] ${(res.text || '').substring(0, 120)}...`
    ).join('\n');
    showResult(text);
  } else {
    showResult(r?.error || 'No results found');
  }
});

$('#chat-btn').addEventListener('click', async () => {
  const content = $('#chat-input').value.trim();
  if (!content) return;
  showResult('Thinking...');
  const r = await msg({
    action: 'tensorZeroChat',
    model: 'claude-sonnet-4-5',
    messages: [{ role: 'user', content }],
  });
  const reply = r?.choices?.[0]?.message?.content || r?.error || JSON.stringify(r);
  showResult(reply);
});

$('#tts-btn').addEventListener('click', async () => {
  const text = $('#tts-input').value.trim();
  if (!text) return;
  showResult('Synthesizing...');
  const r = await msg({ action: 'fluteSynthesize', text, opts: {} });
  showResult(r?.error ? `Error: ${r.error}` : `Audio: ${r?.duration_seconds ?? '?'}s, format: ${r?.format ?? 'pcm16'}`);
});

$('#chit-btn').addEventListener('click', async () => {
  const raw = $('#chit-input').value.trim();
  if (!raw) return;
  showChitResult('Decoding...');
  const ids = raw.split(',').map(s => s.trim()).filter(Boolean);
  const r = await msg({ action: 'chitDecodeText', constellationIds: ids, perConstellation: 10 });
  if (r?.items?.length) {
    const text = r.items.map((it, i) =>
      `${i + 1}. [${(it.score || 0).toFixed(3)}] ${(it.text || '').substring(0, 120)}...`
    ).join('\n');
    showChitResult(text);
  } else {
    showChitResult(r?.error || 'No decoded items');
  }
});

// ─── Agent Tasks ────────────────────────────────

$('#agent-task-btn').addEventListener('click', async () => {
  const message = $('#agent-task-input').value.trim();
  if (!message) return;
  const btn = $('#agent-task-btn');
  btn.disabled = true;
  btn.textContent = 'Running...';
  showAgentResult('Submitting task to Agent Zero (may take minutes)...');
  const r = await msg({ action: 'agentZeroSubmitTask', message });
  if (r?.error) {
    showAgentResult(`Error: ${r.error}`);
  } else {
    showAgentResult(JSON.stringify(r, null, 2));
  }
  btn.disabled = false;
  btn.textContent = 'Run';
});

// ─── CHIT Pipeline ──────────────────────────────

$('#chit-demo-btn').addEventListener('click', async () => {
  const url = $('#chit-demo-url').value.trim();
  if (!url) return;
  showChitResult('Running CHIT pipeline (up to 60s)...');
  const r = await msg({ action: 'chitDemoRun', youtubeUrl: url });
  if (r?.shape) {
    const cal = r.shape.calibration || {};
    const text = [
      `Video: ${r.video?.title || '?'} (${r.video?.segments_indexed || 0} segments)`,
      `Shape: ${r.shape.shape_id}`,
      `Constellations: ${(r.shape.constellations || []).join(', ')}`,
      `Calibration: KL=${cal.KL?.toFixed(4) || '?'} JS=${cal.JS?.toFixed(4) || '?'} coverage=${cal.coverage?.toFixed(2) || '?'}`,
      r.shape.decode?.items?.length ? `Decoded: ${r.shape.decode.items.length} items` : '',
    ].filter(Boolean).join('\n');
    showChitResult(text);
    refreshShapes();
  } else {
    showChitResult(r?.error || JSON.stringify(r));
  }
});

async function refreshShapes() {
  try {
    const r = await msg({ action: 'chitRecentShapes', limit: 5 });
    const list = $('#chit-shapes-list');
    if (!r?.shapes?.length) {
      list.innerHTML = '';
      return;
    }
    list.innerHTML = r.shapes.map(s => `
      <div class="shape-item">
        <span class="shape-label">${escapeHtml(s.label || s.shape_id)}</span>
        <span class="shape-time">${timeAgo(s.created_at)}</span>
        <a href="#" class="shape-svg-link" data-shape-id="${escapeHtml(s.shape_id)}">SVG</a>
      </div>
    `).join('');
    // Wire SVG links
    list.querySelectorAll('.shape-svg-link').forEach(link => {
      link.addEventListener('click', async (e) => {
        e.preventDefault();
        const r = await msg({ action: 'getShapeSvgUrl', shapeId: link.dataset.shapeId });
        if (r?.url) chrome.tabs.create({ url: r.url });
      });
    });
  } catch { /* ignore */ }
}

// Enter key handlers
['ingest-url', 'rag-query', 'chat-input', 'tts-input', 'agent-task-input', 'chit-demo-url', 'chit-input'].forEach(id => {
  $(`#${id}`).addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const btnMap = {
        'ingest-url': 'ingest-btn',
        'rag-query': 'rag-btn',
        'chat-input': 'chat-btn',
        'tts-input': 'tts-btn',
        'agent-task-input': 'agent-task-btn',
        'chit-demo-url': 'chit-demo-btn',
        'chit-input': 'chit-btn',
      };
      $(`#${btnMap[id]}`).click();
    }
  });
});

// ─── Recent Activity ─────────────────────────────

async function refreshHistory() {
  const history = await msg({ action: 'getProcessingHistory' });
  const list = $('#activity-list');

  if (!history?.length) {
    list.innerHTML = '<div class="activity-empty">No recent activity</div>';
    return;
  }

  list.innerHTML = history.slice(0, 5).map(item => `
    <div class="activity-item">
      <span class="activity-id">${escapeHtml(item.videoId || 'URL')}</span>
      <span class="activity-status ${item.status}">${item.status}</span>
      <span class="activity-time">${timeAgo(item.timestamp)}</span>
    </div>
  `).join('');
}

// ─── Footer ──────────────────────────────────────

$('#settings-link').addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

$('#help-btn').addEventListener('click', () => {
  chrome.tabs.create({ url: chrome.runtime.getURL('help/help.html') });
});

$('#refresh-btn').addEventListener('click', () => {
  refreshHealth();
  refreshGpu();
  refreshHistory();
  refreshShapes();
});

// ─── Utilities ───────────────────────────────────

function msg(payload) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(payload, (response) => {
      if (chrome.runtime.lastError) {
        resolve({ error: chrome.runtime.lastError.message });
      } else {
        resolve(response);
      }
    });
  });
}

function showResult(text) {
  const el = $('#action-result');
  el.textContent = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
  el.style.display = 'block';
}

function showAgentResult(text) {
  const el = $('#agent-task-result');
  el.textContent = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
  el.style.display = 'block';
}

function showChitResult(text) {
  const el = $('#chit-result');
  el.textContent = typeof text === 'string' ? text : JSON.stringify(text, null, 2);
  el.style.display = 'block';
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─── Init ────────────────────────────────────────

refreshHealth();
refreshGpu();
refreshHistory();
refreshShapes();
