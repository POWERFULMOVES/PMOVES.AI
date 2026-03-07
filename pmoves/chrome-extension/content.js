// PMOVES.AI YouTube Content Script
// Injects floating button, thumbnail buttons, and action menu on YouTube pages.

(function () {
  'use strict';

  let extensionConfig = null;

  // Load config from background
  chrome.runtime.sendMessage({ action: 'getConfig' }, (cfg) => {
    if (chrome.runtime.lastError) return;
    extensionConfig = cfg;
    init();
  });

  // ─── Floating Action Button ────────────────────

  function createFloatingButton() {
    if (!extensionConfig?.features?.showFloatingButton) return;
    if (document.getElementById('pmoves-float-button')) return;

    const btn = document.createElement('div');
    btn.id = 'pmoves-float-button';
    btn.className = 'pmoves-float-button';
    btn.title = 'PMOVES.AI Actions';
    btn.innerHTML = `
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
      </svg>
      <span class="pmoves-gpu-badge" id="pmoves-gpu-badge" style="display:none;"></span>
    `;
    btn.addEventListener('click', toggleActionMenu);
    document.body.appendChild(btn);

    // Periodically update GPU badge
    updateGpuBadge();
    setInterval(updateGpuBadge, 30000);
  }

  async function updateGpuBadge() {
    try {
      const badge = document.getElementById('pmoves-gpu-badge');
      if (!badge) return;
      chrome.runtime.sendMessage({ action: 'getGpuMetrics' }, (data) => {
        if (chrome.runtime.lastError || !data || data.error) {
          badge.style.display = 'none';
          return;
        }
        const pct = data.vram_usage_percent ?? data.utilization_percent;
        if (pct != null) {
          badge.textContent = `${Math.round(pct)}%`;
          badge.style.display = 'flex';
          badge.style.background = pct > 90 ? '#f44336' : pct > 70 ? '#FF9800' : '#4CAF50';
        }
      });
    } catch { /* silent */ }
  }

  // ─── Action Menu ───────────────────────────────

  function toggleActionMenu(e) {
    e.stopPropagation();
    const existing = document.getElementById('pmoves-action-menu');
    if (existing) { existing.remove(); return; }

    const menu = document.createElement('div');
    menu.id = 'pmoves-action-menu';
    menu.className = 'pmoves-action-menu';

    const actions = [
      { icon: '&#9654;', label: 'Process Current Video', fn: processCurrentVideo },
      { icon: '&#128269;', label: 'Search Knowledge (Hi-RAG)', fn: openSearchOverlay },
      { icon: '&#129302;', label: 'Summarize with AI', fn: summarizeCurrentVideo },
      { icon: '&#128266;', label: 'Read Aloud (TTS)', fn: ttsCurrentPage },
      { icon: '&#128250;', label: 'Process All on Page', fn: processAllVideos },
      { icon: '&#128225;', label: 'Monitor Channel', fn: monitorCurrentChannel },
      { icon: '&#128337;', label: 'Processing History', fn: viewHistory },
      { icon: '&#9881;', label: 'Settings', fn: openSettings },
    ];

    actions.forEach(({ icon, label, fn }) => {
      const item = document.createElement('div');
      item.className = 'pmoves-menu-item';
      item.innerHTML = `<span class="pmoves-menu-icon">${icon}</span>${label}`;
      item.addEventListener('click', (ev) => { ev.stopPropagation(); menu.remove(); fn(); });
      menu.appendChild(item);
    });

    // Position near button
    const btnRect = document.getElementById('pmoves-float-button').getBoundingClientRect();
    menu.style.bottom = `${window.innerHeight - btnRect.top + 10}px`;
    menu.style.right = `${window.innerWidth - btnRect.right}px`;
    document.body.appendChild(menu);

    // Close on outside click
    setTimeout(() => {
      document.addEventListener('click', function close(ev) {
        if (!menu.contains(ev.target)) {
          menu.remove();
          document.removeEventListener('click', close);
        }
      });
    }, 50);
  }

  // ─── Thumbnail Buttons ─────────────────────────

  function addThumbnailButtons() {
    if (!extensionConfig?.features?.showThumbnailButtons) return;

    const thumbnails = document.querySelectorAll('ytd-thumbnail:not(.pmoves-processed)');
    thumbnails.forEach((thumb) => {
      thumb.classList.add('pmoves-processed');
      const link = thumb.querySelector('a');
      if (!link) return;
      const href = link.getAttribute('href');
      if (!href || !href.includes('/watch')) return;
      const videoUrl = `https://www.youtube.com${href}`;

      const btn = document.createElement('div');
      btn.className = 'pmoves-thumbnail-button';
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" stroke-width="2.5"/></svg>`;
      btn.title = 'Process with PMOVES.AI';
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        processVideo(videoUrl);
      });
      thumb.style.position = 'relative';
      thumb.appendChild(btn);
    });
  }

  // ─── Actions ───────────────────────────────────

  function processCurrentVideo() {
    processVideo(window.location.href);
  }

  function processVideo(url) {
    chrome.runtime.sendMessage({ action: 'processVideo', url }, (response) => {
      if (chrome.runtime.lastError) { showToast('Extension error'); return; }
      if (response?.status === 'queued') showToast('Video queued for processing');
      else if (response?.status === 'already_processing') showToast('Already processing');
      else showToast(response?.error || 'Sent to PMOVES.AI');
    });
  }

  function processAllVideos() {
    const links = document.querySelectorAll('a[href*="/watch?v="]');
    const urls = [...new Set([...links].map(l => `https://www.youtube.com${l.getAttribute('href')}`))];
    if (!urls.length) { showToast('No videos found on page'); return; }

    showToast(`Queueing ${urls.length} videos...`);
    urls.forEach(u => processVideo(u));
  }

  function monitorCurrentChannel() {
    const channelEl = document.querySelector('ytd-channel-name a, #channel-name a');
    if (channelEl) {
      const channelUrl = `https://www.youtube.com${channelEl.getAttribute('href')}`;
      processVideo(channelUrl);
      showToast('Channel sent for monitoring');
    } else {
      showToast('Could not identify channel');
    }
  }

  function summarizeCurrentVideo() {
    const title = document.querySelector('h1.ytd-watch-metadata yt-formatted-string')?.textContent || '';
    const desc = document.querySelector('#description-inline-expander yt-attributed-string')?.textContent || '';
    const text = `Summarize this YouTube video:\nTitle: ${title}\nDescription: ${desc}`;

    chrome.runtime.sendMessage({
      action: 'tensorZeroChat',
      model: 'claude-sonnet-4-5',
      messages: [{ role: 'user', content: text }],
    }, (response) => {
      if (chrome.runtime.lastError || response?.error) {
        showToast('AI summarization failed');
        return;
      }
      const content = response?.choices?.[0]?.message?.content || JSON.stringify(response);
      showResultModal('AI Summary', content);
    });
  }

  function ttsCurrentPage() {
    const title = document.querySelector('h1.ytd-watch-metadata yt-formatted-string')?.textContent || 'Hello from PMOVES';
    chrome.runtime.sendMessage({
      action: 'fluteSynthesize',
      text: title.substring(0, 200),
      opts: {},
    }, (response) => {
      if (chrome.runtime.lastError || response?.error) {
        showToast('TTS failed: ' + (response?.error || 'unknown'));
        return;
      }
      showToast('TTS synthesis requested');
    });
  }

  // ─── Search Overlay (Hi-RAG) ───────────────────

  function openSearchOverlay() {
    if (document.getElementById('pmoves-search-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'pmoves-search-overlay';
    overlay.className = 'pmoves-modal';
    overlay.innerHTML = `
      <div class="pmoves-modal-content pmoves-search-modal">
        <h2>Search Knowledge Base</h2>
        <div class="pmoves-search-input-row">
          <input type="text" id="pmoves-search-input" placeholder="Ask anything..." autofocus />
          <button id="pmoves-search-btn" class="pmoves-close-button">Search</button>
        </div>
        <div id="pmoves-search-results" class="pmoves-history-list"></div>
        <button class="pmoves-close-button pmoves-close-modal">Close</button>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector('.pmoves-close-modal').addEventListener('click', () => overlay.remove());
    overlay.querySelector('#pmoves-search-btn').addEventListener('click', doSearch);
    overlay.querySelector('#pmoves-search-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') doSearch();
    });

    async function doSearch() {
      const input = overlay.querySelector('#pmoves-search-input');
      const resultsDiv = overlay.querySelector('#pmoves-search-results');
      const query = input.value.trim();
      if (!query) return;
      resultsDiv.innerHTML = '<div class="pmoves-history-item">Searching...</div>';

      chrome.runtime.sendMessage({
        action: 'hiragQuery',
        query,
        topK: 10,
        rerank: true,
      }, (response) => {
        if (chrome.runtime.lastError || response?.error) {
          resultsDiv.innerHTML = `<div class="pmoves-history-item pmoves-status-failed">Error: ${response?.error || 'unknown'}</div>`;
          return;
        }
        const results = response?.results || [];
        if (!results.length) {
          resultsDiv.innerHTML = '<div class="pmoves-history-item">No results found.</div>';
          return;
        }
        resultsDiv.innerHTML = results.map((r, i) => `
          <div class="pmoves-history-item">
            <div class="pmoves-history-title">#${i + 1} (score: ${(r.score || 0).toFixed(3)})</div>
            <div style="font-size:13px;color:#555;margin-top:4px;">${escapeHtml(r.text?.substring(0, 300) || '')}</div>
          </div>
        `).join('');
      });
    }
  }

  // ─── History Modal ─────────────────────────────

  function viewHistory() {
    chrome.runtime.sendMessage({ action: 'getProcessingHistory' }, (history) => {
      if (chrome.runtime.lastError) return;
      showHistoryModal(history || []);
    });
  }

  function showHistoryModal(history) {
    const modal = document.createElement('div');
    modal.className = 'pmoves-modal';
    modal.innerHTML = `
      <div class="pmoves-modal-content">
        <h2>Processing History</h2>
        <div class="pmoves-history-list">
          ${history.length ? history.map(item => `
            <div class="pmoves-history-item">
              <div class="pmoves-history-title">${escapeHtml(item.videoId || item.url)}</div>
              <div class="pmoves-history-meta">
                <span class="pmoves-status-${item.status}">${item.status}</span>
                <span>${new Date(item.timestamp).toLocaleString()}</span>
              </div>
            </div>
          `).join('') : '<div class="pmoves-history-item">No history yet.</div>'}
        </div>
        <button class="pmoves-close-button">Close</button>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.pmoves-close-button').addEventListener('click', () => modal.remove());
  }

  function showResultModal(title, content) {
    const modal = document.createElement('div');
    modal.className = 'pmoves-modal';
    modal.innerHTML = `
      <div class="pmoves-modal-content">
        <h2>${escapeHtml(title)}</h2>
        <div style="white-space:pre-wrap;font-size:14px;line-height:1.6;max-height:60vh;overflow:auto;">
          ${escapeHtml(content)}
        </div>
        <button class="pmoves-close-button" style="margin-top:16px;">Close</button>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('.pmoves-close-button').addEventListener('click', () => modal.remove());
  }

  // ─── Settings ──────────────────────────────────

  function openSettings() {
    chrome.runtime.sendMessage({ action: 'openSettings' });
  }

  // ─── Utilities ─────────────────────────────────

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'pmoves-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('pmoves-toast-show'));
    setTimeout(() => {
      toast.classList.remove('pmoves-toast-show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ─── Init & Observers ─────────────────────────

  function init() {
    createFloatingButton();
    addThumbnailButtons();

    // Watch for YouTube SPA navigation and new thumbnails
    const observer = new MutationObserver(() => {
      addThumbnailButtons();
      // Re-add floating button after SPA navigation
      if (!document.getElementById('pmoves-float-button')) {
        createFloatingButton();
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  // If config loaded synchronously (cached), init immediately
  if (document.readyState !== 'loading') {
    // Config will init via callback above
  } else {
    document.addEventListener('DOMContentLoaded', () => {});
  }
})();
