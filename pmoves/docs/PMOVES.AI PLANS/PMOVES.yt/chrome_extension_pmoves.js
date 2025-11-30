// ============================================
// PMOVES.AI Chrome Extension
// One-click YouTube video processing
// ============================================

// manifest.json
const manifest = {
  "manifest_version": 3,
  "name": "PMOVES.AI YouTube RAG Processor",
  "version": "1.0.0",
  "description": "One-click processing of YouTube videos with CoCa-enhanced RAG",
  "permissions": [
    "activeTab",
    "storage",
    "notifications",
    "contextMenus"
  ],
  "host_permissions": [
    "https://www.youtube.com/*",
    "https://youtube.com/*",
    "http://localhost:8000/*",
    "http://localhost:8081/*"
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["*://www.youtube.com/*", "*://youtube.com/*"],
      "js": ["content.js"],
      "css": ["styles.css"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "32": "icons/icon32.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "32": "icons/icon32.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  },
  "options_page": "options.html"
};

// ============================================
// background.js - Service Worker
// ============================================
const backgroundJS = `
// Configuration
let config = {
  apiUrl: 'http://localhost:8000',
  queueUrl: 'http://localhost:8081',
  autoProcess: true,
  showNotifications: true,
  processingPriority: 1,
  batchMode: false,
  batchSize: 5
};

// Load config from storage
chrome.storage.sync.get(['pmovesConfig'], (result) => {
  if (result.pmovesConfig) {
    config = { ...config, ...result.pmovesConfig };
  }
});

// Track processing status
const processingStatus = new Map();

// Create context menu items
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'process-video',
    title: 'Process with PMOVES.AI',
    contexts: ['link', 'page'],
    documentUrlPatterns: ['*://www.youtube.com/*', '*://youtube.com/*']
  });
  
  chrome.contextMenus.create({
    id: 'process-channel',
    title: 'Monitor This Channel',
    contexts: ['page'],
    documentUrlPatterns: ['*://www.youtube.com/c/*', '*://www.youtube.com/channel/*', '*://www.youtube.com/@*']
  });
  
  chrome.contextMenus.create({
    id: 'process-playlist',
    title: 'Process Entire Playlist',
    contexts: ['page'],
    documentUrlPatterns: ['*://www.youtube.com/playlist*']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  switch (info.menuItemId) {
    case 'process-video':
      processVideo(info.linkUrl || tab.url);
      break;
    case 'process-channel':
      monitorChannel(tab.url);
      break;
    case 'process-playlist':
      processPlaylist(tab.url);
      break;
  }
});

// Process single video
async function processVideo(url) {
  const videoId = extractVideoId(url);
  
  if (!videoId) {
    showNotification('Invalid URL', 'Could not extract video ID');
    return;
  }
  
  // Check if already processing
  if (processingStatus.has(videoId)) {
    showNotification('Already Processing', 'This video is already being processed');
    return;
  }
  
  processingStatus.set(videoId, 'queued');
  
  try {
    const response = await fetch(\`\${config.queueUrl}/queue/add\`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        urls: [url],
        priority: config.processingPriority,
        source: 'chrome_extension'
      })
    });
    
    const result = await response.json();
    
    if (response.ok) {
      processingStatus.set(videoId, 'processing');
      showNotification('Video Queued', 'Video has been added to processing queue');
      
      // Update badge
      chrome.action.setBadgeText({ text: String(result.queue_size || '1') });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
      
      // Store in history
      storeInHistory(url, videoId);
      
      // Start polling for status
      pollProcessingStatus(videoId);
    } else {
      throw new Error(result.error || 'Failed to queue video');
    }
  } catch (error) {
    processingStatus.delete(videoId);
    showNotification('Error', error.message);
    console.error('Error processing video:', error);
  }
}

// Monitor channel
async function monitorChannel(url) {
  try {
    const response = await fetch(\`\${config.apiUrl}/api/monitor/channel\`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        auto_process: config.autoProcess,
        check_interval: 60
      })
    });
    
    const result = await response.json();
    
    if (response.ok) {
      showNotification('Channel Added', 'Channel will be monitored for new videos');
    } else {
      throw new Error(result.detail || 'Failed to add channel');
    }
  } catch (error) {
    showNotification('Error', error.message);
    console.error('Error monitoring channel:', error);
  }
}

// Process playlist
async function processPlaylist(url) {
  try {
    // Get playlist ID
    const playlistId = new URL(url).searchParams.get('list');
    
    if (!playlistId) {
      throw new Error('Invalid playlist URL');
    }
    
    // Fetch playlist videos (would need YouTube API or scraping)
    // For now, send to backend to handle
    const response = await fetch(\`\${config.apiUrl}/api/playlist/process\`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        playlist_url: url,
        batch_size: config.batchSize
      })
    });
    
    const result = await response.json();
    
    if (response.ok) {
      showNotification(
        'Playlist Queued',
        \`\${result.video_count} videos added to processing queue\`
      );
    } else {
      throw new Error(result.error || 'Failed to process playlist');
    }
  } catch (error) {
    showNotification('Error', error.message);
    console.error('Error processing playlist:', error);
  }
}

// Poll for processing status
async function pollProcessingStatus(videoId) {
  const maxAttempts = 60; // 5 minutes at 5-second intervals
  let attempts = 0;
  
  const interval = setInterval(async () => {
    attempts++;
    
    try {
      const response = await fetch(\`\${config.apiUrl}/api/video/status/\${videoId}\`);
      const status = await response.json();
      
      if (status.processing_status === 'completed') {
        processingStatus.set(videoId, 'completed');
        showNotification('Processing Complete', \`Video \${videoId} has been processed\`);
        clearInterval(interval);
        
        // Clear badge after success
        setTimeout(() => {
          chrome.action.setBadgeText({ text: '' });
        }, 3000);
      } else if (status.processing_status === 'failed') {
        processingStatus.set(videoId, 'failed');
        showNotification('Processing Failed', status.error || 'Unknown error');
        clearInterval(interval);
      }
      
      if (attempts >= maxAttempts) {
        clearInterval(interval);
      }
    } catch (error) {
      console.error('Error polling status:', error);
      if (attempts >= maxAttempts) {
        clearInterval(interval);
      }
    }
  }, 5000);
}

// Store in processing history
function storeInHistory(url, videoId) {
  chrome.storage.local.get(['processingHistory'], (result) => {
    const history = result.processingHistory || [];
    
    history.unshift({
      url,
      videoId,
      timestamp: new Date().toISOString(),
      status: 'processing'
    });
    
    // Keep only last 100 items
    if (history.length > 100) {
      history.pop();
    }
    
    chrome.storage.local.set({ processingHistory: history });
  });
}

// Extract video ID from URL
function extractVideoId(url) {
  const regex = /(?:youtube\\.com\\/watch\\?v=|youtu\\.be\\/)([^&\\n]+)/;
  const match = url.match(regex);
  return match ? match[1] : null;
}

// Show notification
function showNotification(title, message) {
  if (config.showNotifications) {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: title,
      message: message
    });
  }
}

// Handle messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'processVideo':
      processVideo(request.url);
      sendResponse({ status: 'queued' });
      break;
      
    case 'getStatus':
      sendResponse({
        status: processingStatus.get(request.videoId) || 'unknown'
      });
      break;
      
    case 'getConfig':
      sendResponse(config);
      break;
      
    case 'updateConfig':
      config = { ...config, ...request.config };
      chrome.storage.sync.set({ pmovesConfig: config });
      sendResponse({ status: 'updated' });
      break;
      
    case 'getProcessingHistory':
      chrome.storage.local.get(['processingHistory'], (result) => {
        sendResponse(result.processingHistory || []);
      });
      return true; // Keep channel open for async response
      
    default:
      sendResponse({ error: 'Unknown action' });
  }
});
`;

// ============================================
// content.js - Content Script
// ============================================
const contentJS = `
// PMOVES.AI YouTube Content Script
console.log('PMOVES.AI YouTube RAG Processor loaded');

// Configuration
let extensionConfig = null;

// Load configuration
chrome.runtime.sendMessage({ action: 'getConfig' }, (config) => {
  extensionConfig = config;
});

// Create floating action button
function createFloatingButton() {
  const button = document.createElement('div');
  button.id = 'pmoves-float-button';
  button.className = 'pmoves-float-button';
  button.innerHTML = \`
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2"/>
      <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2"/>
      <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2"/>
    </svg>
  \`;
  
  button.addEventListener('click', handleFloatingButtonClick);
  
  document.body.appendChild(button);
}

// Create inline process button for video thumbnails
function createInlineButtons() {
  // For video pages
  if (window.location.pathname === '/watch') {
    addVideoPageButton();
  }
  
  // For video thumbnails in lists
  const observer = new MutationObserver(() => {
    addThumbnailButtons();
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
  
  // Initial run
  addThumbnailButtons();
}

// Add button to video page
function addVideoPageButton() {
  const targetElement = document.querySelector('#owner');
  
  if (targetElement && !document.querySelector('#pmoves-video-button')) {
    const button = document.createElement('button');
    button.id = 'pmoves-video-button';
    button.className = 'pmoves-process-button';
    button.innerHTML = \`
      <span class="pmoves-icon">🚀</span>
      <span>Process with PMOVES</span>
    \`;
    
    button.addEventListener('click', () => {
      processCurrentVideo();
    });
    
    targetElement.parentElement.insertBefore(button, targetElement.nextSibling);
  }
}

// Add buttons to video thumbnails
function addThumbnailButtons() {
  const thumbnails = document.querySelectorAll('ytd-thumbnail:not(.pmoves-processed)');
  
  thumbnails.forEach((thumbnail) => {
    thumbnail.classList.add('pmoves-processed');
    
    const link = thumbnail.querySelector('a');
    if (!link) return;
    
    const videoUrl = \`https://www.youtube.com\${link.getAttribute('href')}\`;
    const videoId = extractVideoIdFromUrl(videoUrl);
    
    if (!videoId) return;
    
    const button = document.createElement('div');
    button.className = 'pmoves-thumbnail-button';
    button.innerHTML = '🚀';
    button.title = 'Process with PMOVES.AI';
    
    button.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      processVideo(videoUrl);
    });
    
    thumbnail.appendChild(button);
  });
}

// Handle floating button click
function handleFloatingButtonClick() {
  const menu = createActionMenu();
  document.body.appendChild(menu);
  
  // Remove menu on outside click
  setTimeout(() => {
    document.addEventListener('click', function removeMenu(e) {
      if (!menu.contains(e.target)) {
        menu.remove();
        document.removeEventListener('click', removeMenu);
      }
    });
  }, 100);
}

// Create action menu
function createActionMenu() {
  const menu = document.createElement('div');
  menu.className = 'pmoves-action-menu';
  
  const actions = [
    { label: 'Process Current Video', action: processCurrentVideo },
    { label: 'Process All Videos on Page', action: processAllVideos },
    { label: 'Monitor This Channel', action: monitorCurrentChannel },
    { label: 'View Processing History', action: viewHistory },
    { label: 'Settings', action: openSettings }
  ];
  
  actions.forEach(({ label, action }) => {
    const item = document.createElement('div');
    item.className = 'pmoves-menu-item';
    item.textContent = label;
    item.addEventListener('click', action);
    menu.appendChild(item);
  });
  
  // Position menu near button
  const button = document.querySelector('#pmoves-float-button');
  const rect = button.getBoundingClientRect();
  menu.style.bottom = (window.innerHeight - rect.top + 10) + 'px';
  menu.style.right = (window.innerWidth - rect.right) + 'px';
  
  return menu;
}

// Process current video
function processCurrentVideo() {
  const url = window.location.href;
  processVideo(url);
}

// Process all videos on page
function processAllVideos() {
  const links = document.querySelectorAll('a[href*="/watch?v="]');
  const urls = Array.from(new Set(
    Array.from(links).map(link => \`https://www.youtube.com\${link.getAttribute('href')}\`)
  ));
  
  if (urls.length === 0) {
    showToast('No videos found on page');
    return;
  }
  
  const confirmed = confirm(\`Process \${urls.length} videos?\`);
  if (confirmed) {
    urls.forEach(url => processVideo(url));
    showToast(\`Queued \${urls.length} videos for processing\`);
  }
}

// Process video
function processVideo(url) {
  chrome.runtime.sendMessage(
    { action: 'processVideo', url },
    (response) => {
      if (response.status === 'queued') {
        showToast('Video queued for processing');
        updateButtonStatus(url, 'processing');
      }
    }
  );
}

// Monitor current channel
function monitorCurrentChannel() {
  const channelElement = document.querySelector('ytd-channel-name a');
  
  if (channelElement) {
    const channelUrl = \`https://www.youtube.com\${channelElement.getAttribute('href')}\`;
    
    chrome.runtime.sendMessage(
      { action: 'monitorChannel', url: channelUrl },
      (response) => {
        showToast('Channel added to monitoring');
      }
    );
  } else {
    showToast('Could not identify channel');
  }
}

// View processing history
function viewHistory() {
  chrome.runtime.sendMessage(
    { action: 'getProcessingHistory' },
    (history) => {
      showHistoryModal(history);
    }
  );
}

// Show history modal
function showHistoryModal(history) {
  const modal = document.createElement('div');
  modal.className = 'pmoves-modal';
  
  const content = document.createElement('div');
  content.className = 'pmoves-modal-content';
  
  content.innerHTML = \`
    <h2>Processing History</h2>
    <div class="pmoves-history-list">
      \${history.map(item => \`
        <div class="pmoves-history-item">
          <div class="pmoves-history-title">\${getVideoTitle(item.url)}</div>
          <div class="pmoves-history-meta">
            <span class="pmoves-status-\${item.status}">\${item.status}</span>
            <span>\${formatDate(item.timestamp)}</span>
          </div>
        </div>
      \`).join('')}
    </div>
    <button class="pmoves-close-button">Close</button>
  \`;
  
  modal.appendChild(content);
  document.body.appendChild(modal);
  
  content.querySelector('.pmoves-close-button').addEventListener('click', () => {
    modal.remove();
  });
}

// Open settings
function openSettings() {
  chrome.runtime.sendMessage({ action: 'openSettings' });
}

// Show toast notification
function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'pmoves-toast';
  toast.textContent = message;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('pmoves-toast-show');
  }, 100);
  
  setTimeout(() => {
    toast.classList.remove('pmoves-toast-show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Update button status
function updateButtonStatus(url, status) {
  const videoId = extractVideoIdFromUrl(url);
  const button = document.querySelector(\`[data-video-id="\${videoId}"]\`);
  
  if (button) {
    button.classList.remove('pmoves-status-pending', 'pmoves-status-processing', 'pmoves-status-completed');
    button.classList.add(\`pmoves-status-\${status}\`);
  }
}

// Utility functions
function extractVideoIdFromUrl(url) {
  const regex = /(?:youtube\\.com\\/watch\\?v=|youtu\\.be\\/)([^&\\n]+)/;
  const match = url.match(regex);
  return match ? match[1] : null;
}

function getVideoTitle(url) {
  // Would need to fetch or extract from page
  return 'Video';
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString();
}

// Initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

function init() {
  createFloatingButton();
  createInlineButtons();
}
`;

// ============================================
// styles.css
// ============================================
const stylesCSS = `
/* PMOVES.AI Chrome Extension Styles */

.pmoves-float-button {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 9999;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  color: white;
}

.pmoves-float-button:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

.pmoves-process-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  margin: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.pmoves-process-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.pmoves-thumbnail-button {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 32px;
  height: 32px;
  background: rgba(102, 126, 234, 0.9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.3s ease;
  z-index: 10;
}

ytd-thumbnail:hover .pmoves-thumbnail-button {
  opacity: 1;
}

.pmoves-thumbnail-button:hover {
  background: rgba(102, 126, 234, 1);
  transform: scale(1.1);
}

.pmoves-action-menu {
  position: fixed;
  background: white;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 8px 0;
  z-index: 10000;
  min-width: 200px;
}

.pmoves-menu-item {
  padding: 12px 20px;
  cursor: pointer;
  transition: background 0.2s ease;
  font-size: 14px;
  color: #333;
}

.pmoves-menu-item:hover {
  background: #f5f5f5;
}

.pmoves-toast {
  position: fixed;
  bottom: 100px;
  right: 20px;
  background: #333;
  color: white;
  padding: 12px 20px;
  border-radius: 4px;
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.3s ease;
  z-index: 10000;
}

.pmoves-toast-show {
  opacity: 1;
  transform: translateY(0);
}

.pmoves-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.pmoves-modal-content {
  background: white;
  border-radius: 12px;
  padding: 24px;
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.pmoves-history-list {
  margin: 20px 0;
}

.pmoves-history-item {
  padding: 12px;
  border-bottom: 1px solid #eee;
}

.pmoves-history-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.pmoves-status-processing {
  color: #2196F3;
}

.pmoves-status-completed {
  color: #4CAF50;
}

.pmoves-status-failed {
  color: #f44336;
}

.pmoves-close-button {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
`;

// Export all files as a single object for easy saving
const chromeExtensionFiles = {
  manifest,
  backgroundJS,
  contentJS,
  stylesCSS
};

console.log('Chrome Extension files ready for export');
