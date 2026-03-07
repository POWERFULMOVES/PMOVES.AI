// PMOVES.AI Chrome Extension - Background Service Worker
import { DEFAULT_CONFIG, BADGE_COLORS } from './lib/constants.js';
import {
  setServiceUrls, healthCheckAll, shapeSvgUrl,
  tensorZero, gpu, hirag, yt, agentZero, flute, mesh, chit,
} from './lib/pmoves-api.js';

let config = structuredClone(DEFAULT_CONFIG);
let lastHealth = {};
const processingStatus = new Map();

// ─── Config ──────────────────────────────────────

async function loadConfig() {
  const result = await chrome.storage.sync.get(['pmovesConfig']);
  if (result.pmovesConfig) {
    config = { ...config, ...result.pmovesConfig };
  }
  setServiceUrls(config.services);
}

async function saveConfig() {
  await chrome.storage.sync.set({ pmovesConfig: config });
}

loadConfig();

// ─── Context Menus ───────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'process-video',
    title: 'Process with PMOVES.AI',
    contexts: ['link', 'page'],
    documentUrlPatterns: ['*://www.youtube.com/*', '*://youtube.com/*'],
  });

  chrome.contextMenus.create({
    id: 'monitor-channel',
    title: 'Monitor This Channel',
    contexts: ['page'],
    documentUrlPatterns: [
      '*://www.youtube.com/c/*',
      '*://www.youtube.com/channel/*',
      '*://www.youtube.com/@*',
    ],
  });

  chrome.contextMenus.create({
    id: 'process-playlist',
    title: 'Process Entire Playlist',
    contexts: ['page'],
    documentUrlPatterns: ['*://www.youtube.com/playlist*'],
  });

  // Start health polling
  chrome.alarms.create('health-poll', {
    periodInMinutes: config.features.healthPollInterval / 60,
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const url = info.linkUrl || tab.url;
  switch (info.menuItemId) {
    case 'process-video':
      processVideo(url);
      break;
    case 'monitor-channel':
      // Channel monitoring via PMOVES.YT ingest (channel URL)
      processVideo(tab.url);
      break;
    case 'process-playlist':
      processVideo(tab.url);
      break;
  }
});

// ─── Health Polling ──────────────────────────────

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'health-poll') {
    await pollHealth();
  }
});

async function pollHealth() {
  try {
    lastHealth = await healthCheckAll();
    const okCount = Object.values(lastHealth).filter(h => h.ok).length;
    const total = Object.keys(lastHealth).length;

    if (okCount === total) {
      chrome.action.setBadgeBackgroundColor({ color: BADGE_COLORS.healthy });
      chrome.action.setBadgeText({ text: '' });
    } else if (okCount > 0) {
      chrome.action.setBadgeBackgroundColor({ color: BADGE_COLORS.degraded });
      chrome.action.setBadgeText({ text: `${okCount}/${total}` });
    } else {
      chrome.action.setBadgeBackgroundColor({ color: BADGE_COLORS.down });
      chrome.action.setBadgeText({ text: 'OFF' });
    }
  } catch (e) {
    chrome.action.setBadgeBackgroundColor({ color: BADGE_COLORS.unknown });
    chrome.action.setBadgeText({ text: '?' });
  }
}

// ─── Video Processing ────────────────────────────

function extractVideoId(url) {
  try {
    const m = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/);
    return m ? m[1] : null;
  } catch { return null; }
}

async function processVideo(url) {
  const videoId = extractVideoId(url);

  if (processingStatus.has(videoId || url)) {
    notify('Already Processing', 'This video is already being processed.');
    return { status: 'already_processing' };
  }

  processingStatus.set(videoId || url, 'queued');

  try {
    const result = await yt.ingest(url);
    processingStatus.set(videoId || url, 'processing');
    notify('Video Queued', 'Video sent to PMOVES.YT for ingestion.');
    storeInHistory(url, videoId);

    chrome.action.setBadgeText({ text: '1' });
    chrome.action.setBadgeBackgroundColor({ color: BADGE_COLORS.healthy });
    setTimeout(() => chrome.action.setBadgeText({ text: '' }), 5000);

    return { status: 'queued', result };
  } catch (err) {
    processingStatus.delete(videoId || url);
    notify('Ingestion Error', err.message);
    return { status: 'error', error: err.message };
  }
}

function storeInHistory(url, videoId) {
  chrome.storage.local.get(['processingHistory'], (result) => {
    const history = result.processingHistory || [];
    history.unshift({
      url,
      videoId,
      timestamp: new Date().toISOString(),
      status: 'processing',
    });
    if (history.length > 100) history.length = 100;
    chrome.storage.local.set({ processingHistory: history });
  });
}

function notify(title, message) {
  if (!config.features.showNotifications) return;
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: `PMOVES.AI - ${title}`,
    message,
  });
}

// ─── Message Router ──────────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request).then(sendResponse).catch(err => {
    sendResponse({ error: err.message });
  });
  return true; // keep channel open for async
});

async function handleMessage(req) {
  switch (req.action) {
    // Video processing
    case 'processVideo':
      return processVideo(req.url);

    case 'getStatus':
      return { status: processingStatus.get(req.videoId) || 'unknown' };

    case 'getProcessingHistory': {
      const r = await chrome.storage.local.get(['processingHistory']);
      return r.processingHistory || [];
    }

    // Health
    case 'getHealthStatus':
      if (!Object.keys(lastHealth).length) await pollHealth();
      return lastHealth;

    case 'refreshHealth':
      await pollHealth();
      return lastHealth;

    // Config
    case 'getConfig':
      return config;

    case 'updateConfig':
      config = { ...config, ...req.config };
      setServiceUrls(config.services);
      await saveConfig();
      // Update alarm interval
      chrome.alarms.create('health-poll', {
        periodInMinutes: config.features.healthPollInterval / 60,
      });
      return { status: 'updated' };

    case 'openSettings':
      chrome.runtime.openOptionsPage();
      return { status: 'opened' };

    // GPU Orchestrator
    case 'getGpuStatus':
      return gpu.status();

    case 'getGpuMetrics':
      return gpu.metricsSummary();

    case 'getGpuModels':
      return gpu.models(req.opts);

    case 'gpuLoadModel':
      return gpu.loadModel(req.modelId, req.provider, req.priority);

    case 'gpuUnloadModel':
      return gpu.unloadModel(req.provider, req.modelId, req.force);

    case 'gpuOptimize':
      return gpu.optimize();

    // TensorZero
    case 'tensorZeroChat':
      return tensorZero.chat(req.model, req.messages);

    case 'tensorZeroEmbed':
      return tensorZero.embed(req.model, req.input);

    // Hi-RAG
    case 'hiragQuery':
      return hirag.query(req.query, req.topK, req.rerank, req.opts);

    // Agent Zero
    case 'agentZeroHealth':
      return agentZero.health();

    case 'agentZeroListCommands':
      return agentZero.listCommands(config.auth.agentZeroToken);

    case 'agentZeroExecuteCommand':
      return agentZero.executeCommand(config.auth.agentZeroToken, req.cmd, req.args);

    case 'agentZeroSubmitTask':
      return agentZero.submitTask(config.auth.agentZeroToken, req.message, req.metadata);

    case 'agentZeroGetJobLog':
      return agentZero.getJobLog(config.auth.agentZeroToken, req.contextId, req.length);

    case 'agentZeroSendMessage':
      return agentZero.sendMessage(config.auth.agentZeroToken, req.message, req.contextId);

    case 'agentZeroPublishEvent':
      return agentZero.publishEvent(config.auth.agentZeroToken, req.topic, req.payload);

    // Flute Gateway
    case 'fluteSynthesize':
      return flute.synthesize(config.auth.fluteApiKey, req.text, req.opts);

    case 'flutePersonas':
      return flute.personas(config.auth.fluteApiKey);

    // Mesh Agent (via Prometheus)
    case 'meshStatus':
      return mesh.meshAgentUp();

    // CHIT / Geometry Bus (Gateway)
    case 'chitPublishEvent':
      return chit.publishEvent(req.cgp);

    case 'chitDecodeText':
      return chit.decodeText(req.constellationIds, req.perConstellation, req.shapeId);

    case 'chitCalibrationReport':
      return chit.calibrationReport(req.cgp);

    case 'chitJumpPoint':
      return chit.jumpPoint(req.pid);

    // CHIT Workflow + Visualization
    case 'chitDemoRun':
      return chit.demoRun(req.youtubeUrl, req.opts);

    case 'chitRecentShapes':
      return chit.recentShapes(req.limit);

    case 'chitConstellationIndex':
      return chit.constellationIndex(req.shapeId);

    case 'chitRecentEvents':
      return chit.recentEvents(req.limit);

    case 'getShapeSvgUrl':
      return { url: shapeSvgUrl(req.shapeId) };

    default:
      return { error: `Unknown action: ${req.action}` };
  }
}
