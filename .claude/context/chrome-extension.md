# PMOVES.AI Chrome Extension Integration

**Location:** `pmoves/chrome-extension/`
**Version:** 1.0.0 (Manifest V3)
**Purpose:** YouTube-focused browser client integrating bidirectionally with 8 PMOVES.AI backend services

---

## Overview

The Chrome extension provides one-click YouTube video processing, knowledge search, AI summarization, GPU monitoring, voice synthesis, agent orchestration, and CHIT pipeline visualization — all from within YouTube pages or the popup dashboard.

- **Manifest V3** with ES module service worker
- **4 components:** content script, background service worker, popup dashboard, options page
- **8 service integrations** via `lib/pmoves-api.js`
- **Poll-only architecture** — no WebSocket or NATS subscriptions

---

## Architecture

```
YouTube Page                 Extension                         PMOVES.AI Services
─────────────               ─────────                         ──────────────────
                             ┌──────────────┐
  content.js ──sendMessage──>│ background.js │──fetch──> TensorZero    :3030
  (buttons,                  │ (msg router,  │──fetch──> GPU Orch.     :8200
   menus,                    │  health poll, │──fetch──> Hi-RAG v2     :8086
   overlays)                 │  config mgmt) │──fetch──> PMOVES.YT     :8077
                             └──────┬───────┘──fetch──> Agent Zero    :8080
  popup/      ──sendMessage──>      │         ──fetch──> Flute Gateway :8055
  options/    ──sendMessage──>      │         ──fetch──> Prometheus    :9090
                                    │         ──fetch──> Gateway/CHIT  :8085
                             lib/pmoves-api.js
                             lib/constants.js
```

### Chrome APIs Used

| API | Purpose |
|-----|---------|
| `chrome.storage.sync` | Config persistence (`pmovesConfig` key) |
| `chrome.storage.local` | Processing history (`processingHistory` key) |
| `chrome.alarms` | Health polling loop (default 30s) |
| `chrome.notifications` | Desktop alerts for processing status |
| `chrome.contextMenus` | Right-click: Process Video, Monitor Channel, Process Playlist |
| `chrome.action` | Badge text/color for health status |
| `chrome.runtime.sendMessage` | Inter-component message passing |
| `chrome.tabs` | Active tab URL access |

### Storage Schema

**`chrome.storage.sync.pmovesConfig`:**
```json
{
  "services": {
    "tensorzero": "http://localhost:3030",
    "gpuOrchestrator": "http://localhost:8200",
    "hirag": "http://localhost:8086",
    "pmovesYt": "http://localhost:8077",
    "agentZero": "http://localhost:8080",
    "fluteGateway": "http://localhost:8055",
    "prometheus": "http://localhost:9090",
    "gateway": "http://localhost:8085"
  },
  "auth": {
    "agentZeroToken": "",
    "fluteApiKey": ""
  },
  "features": {
    "autoProcess": false,
    "showFloatingButton": true,
    "showThumbnailButtons": true,
    "showNotifications": true,
    "healthPollInterval": 30
  }
}
```

**`chrome.storage.local.processingHistory`:** Array of `{ url, videoId, timestamp, status }` (max 100 entries).

---

## Extension -> PMOVES.AI (Outbound)

### 1. TensorZero [Port 3030] — No Auth

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| POST | `/v1/chat/completions` | `{ model, messages }` | AI summarization (content.js) |
| POST | `/v1/embeddings` | `{ model, input }` | Embedding generation (popup) |

**Health check:** `GET /v1/models`
**Default timeout:** 8s

### 2. GPU Orchestrator [Port 8200] — No Auth

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| GET | `/api/gpu/status` | — | GPU status panel (popup) |
| GET | `/api/gpu/metrics/summary` | — | GPU badge on floating button (content.js, 30s interval) |
| GET | `/api/gpu/models` | Query: `?provider=&include_unloaded=true` | Model listing (popup) |
| POST | `/api/gpu/models/load` | `{ model_id, provider, priority }` | Model management (popup) |
| POST | `/api/gpu/models/unload/{provider}/{modelId}` | Query: `?force=true` | Model management (popup) |
| POST | `/api/gpu/optimize` | — | GPU optimization (popup) |
| GET | `/api/gpu/queue` | — | Queue view (popup) |

**Health check:** `GET /api/gpu/status`
**Default timeout:** 8s

### 3. Hi-RAG v2 [Port 8086] — No Auth

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| POST | `/hirag/query` | `{ query, top_k, rerank, alpha, graph_boost, entity_types, namespace }` | Knowledge search overlay (content.js), popup |

**Health check:** `GET /`
**Default timeout:** 8s
**Defaults:** `top_k=10`, `rerank=true`, `alpha=0.7`, `graph_boost=0.15`, `namespace="pmoves"`

### 4. PMOVES.YT [Port 8077] — No Auth

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| POST | `/yt/ingest` | `{ url }` | Video processing (content.js buttons, context menus, popup) |
| GET | `/healthz` | — | Health check |

**Health check:** `GET /healthz`
**Default timeout:** 8s
**Downstream:** Triggers `ingest.file.added.v1` and `ingest.transcript.ready.v1` NATS events

### 5. Agent Zero [Port 8080] — Bearer Token

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| GET | `/healthz` | — | Health check |
| GET | `/mcp/commands` | — | List MCP commands (options page) |
| POST | `/mcp/execute` | `{ cmd, arguments }` | Execute MCP command (popup) |
| POST | `/tasks` | `{ message, metadata }` | Submit task (popup, 120s timeout) |
| GET | `/jobs/{contextId}?length=N` | — | Job conversation log (popup) |
| POST | `/sessions` | `{ message, context_id? }` | Conversational message (popup, 120s timeout) |
| POST | `/events/publish` | `{ topic, payload, source: "chrome-extension" }` | Publish NATS event (popup) |

**Auth:** `Authorization: Bearer {agentZeroToken}`
**Health check:** `GET /healthz`
**Note:** Tasks and sessions have extended 120s timeout for long-running agent operations.

### 6. Flute Gateway [Port 8055] — X-API-Key

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| POST | `/v1/voice/synthesize` | `{ text, persona_id?, provider?, voice?, engine?, output_format? }` | TTS synthesis (content.js, popup) |
| POST | `/v1/voice/synthesize/audio` | Same as above | Direct audio buffer (popup) |
| GET | `/v1/voice/personas` | — | Persona listing (popup) |
| GET | `/v1/voice/config` | — | Voice config (popup) |

**Auth:** `X-API-Key: {fluteApiKey}`
**Health check:** `GET /healthz`
**Default timeout:** 8s

### 7. Prometheus [Port 9090] — No Auth

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| GET | `/api/v1/query?query=up` | — | All services status (popup) |
| GET | `/api/v1/query?query=up{job="mesh-agent"}` | — | Mesh agent status (popup) |

**Health check:** `GET /-/healthy`
**Default timeout:** 5s

### 8. Gateway / CHIT [Port 8085] — No Auth

| Method | Path | Request Body | Used By |
|--------|------|-------------|---------|
| POST | `/geometry/event` | `{ type: "geometry.cgp.v1", data: <cgp> }` | Publish CGP event (popup) |
| POST | `/geometry/decode/text` | `{ shape_id?, constellation_ids[], per_constellation }` | Decode text (popup) |
| POST | `/geometry/calibration/report` | `<cgp object>` | Calibration report (popup) |
| GET | `/shape/point/{pid}/jump` | — | Jump point lookup (popup) |
| POST | `/workflow/demo_run` | `{ youtube_url, ...opts }` | Full CHIT pipeline (popup, 60s timeout) |
| GET | `/viz/recent?limit=N` | — | Recent shapes (popup, options) |
| GET | `/viz/shape/{shapeId}/constellations` | — | Constellation index (popup) |
| GET | `/events/recent?limit=N` | — | Recent NATS events (popup, options) |
| GET | `/viz/shape/{shapeId}.svg` | — | Shape SVG rendering (popup) |

**Health check:** `GET /`
**Default timeout:** 8s (60s for `demo_run`)

---

## PMOVES.AI -> Extension (Inbound)

The extension is **poll-only** — there are no WebSocket connections, NATS subscriptions, or push notifications from services.

### Health Polling

- **Trigger:** `chrome.alarms` alarm named `health-poll`
- **Default interval:** 30 seconds (configurable via `features.healthPollInterval`)
- **Mechanism:** 8 parallel `fetch()` calls to health endpoints with 5s timeout each
- **Results cached** in `lastHealth` object in background.js

### Badge State Machine

| Condition | Badge Color | Badge Text |
|-----------|------------|------------|
| All 8 services healthy | Green `#4CAF50` | (empty) |
| Partial (1-7 healthy) | Orange `#FF9800` | `X/8` (e.g. `6/8`) |
| All services down | Red `#F44336` | `OFF` |
| Poll error | Grey `#9E9E9E` | `?` |

### GPU Badge (Content Script)

- **Location:** Floating button in YouTube pages
- **Interval:** 30s (`setInterval` in content.js)
- **Data source:** `getGpuMetrics` -> `GET /api/gpu/metrics/summary`
- **Display:** VRAM/utilization percentage with color coding:
  - Green `#4CAF50`: <= 70%
  - Orange `#FF9800`: 71-90%
  - Red `#f44336`: > 90%

### Indirect NATS Visibility

- NATS events are not directly consumed
- Recent events viewable via `GET /events/recent` on Gateway (port 8085)
- Agent Zero's `/events/publish` endpoint allows the extension to **produce** NATS events with `source: "chrome-extension"`

---

## Message Action Reference

Complete table of all `chrome.runtime.sendMessage` actions handled by `background.js handleMessage()`:

| # | Action | Service | Method + Path | Auth | Timeout |
|---|--------|---------|---------------|------|---------|
| 1 | `processVideo` | PMOVES.YT | POST `/yt/ingest` | No | 8s |
| 2 | `getStatus` | (local) | — | — | — |
| 3 | `getProcessingHistory` | (storage) | — | — | — |
| 4 | `getHealthStatus` | All 8 | Health endpoints | No | 5s |
| 5 | `refreshHealth` | All 8 | Health endpoints | No | 5s |
| 6 | `getConfig` | (local) | — | — | — |
| 7 | `updateConfig` | (storage) | — | — | — |
| 8 | `openSettings` | (chrome) | — | — | — |
| 9 | `getGpuStatus` | GPU Orch. | GET `/api/gpu/status` | No | 8s |
| 10 | `getGpuMetrics` | GPU Orch. | GET `/api/gpu/metrics/summary` | No | 8s |
| 11 | `getGpuModels` | GPU Orch. | GET `/api/gpu/models` | No | 8s |
| 12 | `gpuLoadModel` | GPU Orch. | POST `/api/gpu/models/load` | No | 8s |
| 13 | `gpuUnloadModel` | GPU Orch. | POST `/api/gpu/models/unload/...` | No | 8s |
| 14 | `gpuOptimize` | GPU Orch. | POST `/api/gpu/optimize` | No | 8s |
| 15 | `tensorZeroChat` | TensorZero | POST `/v1/chat/completions` | No | 8s |
| 16 | `tensorZeroEmbed` | TensorZero | POST `/v1/embeddings` | No | 8s |
| 17 | `hiragQuery` | Hi-RAG v2 | POST `/hirag/query` | No | 8s |
| 18 | `agentZeroHealth` | Agent Zero | GET `/healthz` | Bearer | 8s |
| 19 | `agentZeroListCommands` | Agent Zero | GET `/mcp/commands` | Bearer | 8s |
| 20 | `agentZeroExecuteCommand` | Agent Zero | POST `/mcp/execute` | Bearer | 8s |
| 21 | `agentZeroSubmitTask` | Agent Zero | POST `/tasks` | Bearer | 120s |
| 22 | `agentZeroGetJobLog` | Agent Zero | GET `/jobs/{id}` | Bearer | 8s |
| 23 | `agentZeroSendMessage` | Agent Zero | POST `/sessions` | Bearer | 120s |
| 24 | `agentZeroPublishEvent` | Agent Zero | POST `/events/publish` | Bearer | 8s |
| 25 | `fluteSynthesize` | Flute | POST `/v1/voice/synthesize` | X-API-Key | 8s |
| 26 | `flutePersonas` | Flute | GET `/v1/voice/personas` | X-API-Key | 8s |
| 27 | `meshStatus` | Prometheus | GET `/api/v1/query` | No | 5s |
| 28 | `chitPublishEvent` | Gateway | POST `/geometry/event` | No | 8s |
| 29 | `chitDecodeText` | Gateway | POST `/geometry/decode/text` | No | 8s |
| 30 | `chitCalibrationReport` | Gateway | POST `/geometry/calibration/report` | No | 8s |
| 31 | `chitJumpPoint` | Gateway | GET `/shape/point/{pid}/jump` | No | 8s |
| 32 | `chitDemoRun` | Gateway | POST `/workflow/demo_run` | No | 60s |
| 33 | `chitRecentShapes` | Gateway | GET `/viz/recent` | No | 8s |
| 34 | `chitConstellationIndex` | Gateway | GET `/viz/shape/{id}/constellations` | No | 8s |
| 35 | `chitRecentEvents` | Gateway | GET `/events/recent` | No | 8s |
| 36 | `getShapeSvgUrl` | (local) | Constructs URL only | — | — |

**Total: 36 actions** (32 make network calls, 4 are local-only)

---

## Authentication

| Service | Mechanism | Header | Storage Key |
|---------|-----------|--------|-------------|
| Agent Zero | Bearer token | `Authorization: Bearer {token}` | `pmovesConfig.auth.agentZeroToken` |
| Flute Gateway | API key | `X-API-Key: {key}` | `pmovesConfig.auth.fluteApiKey` |
| All others | None | — | — |

Credentials are stored in `chrome.storage.sync` and loaded into the background service worker at startup.

---

## Development & Testing

### Mock Server

```bash
cd pmoves/chrome-extension
node test/mock-server.js
```

Simulates all 8 service endpoints on their default ports for local development without the full Docker stack.

### Loading the Extension

1. `chrome://extensions` -> Enable Developer mode
2. "Load unpacked" -> Select `pmoves/chrome-extension/`
3. Navigate to YouTube to see content script injection

### Adding a New Service Integration

Checklist (5 files):

1. **`lib/constants.js`** — Add to `DEFAULT_SERVICES` and `HEALTH_ENDPOINTS`
2. **`lib/pmoves-api.js`** — Add API client module with methods
3. **`background.js`** — Add `case` entries to `handleMessage()` dispatch
4. **`manifest.json`** — Add port to `host_permissions`
5. **UI files** — Add controls to popup and/or options page

---

## Content Script Injection Points (YouTube)

| Element | Selector Target | Feature |
|---------|----------------|---------|
| Floating button | `document.body` (bottom-right fixed) | Action menu with 8 items |
| Thumbnail buttons | `ytd-thumbnail`, `ytd-compact-video-renderer` | Per-video process buttons |
| Search overlay | `document.body` (modal) | Hi-RAG knowledge search |
| History modal | `document.body` (modal) | Processing history view |
| Result modal | `document.body` (modal) | AI summary display |
| Toast notifications | `document.body` (fixed) | Status feedback (max 3) |

The content script uses a `MutationObserver` on `document.body` to handle YouTube's SPA navigation, re-injecting buttons as the DOM updates.
