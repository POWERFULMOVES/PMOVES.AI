# PMOVES.AI Chrome Extension

One-click YouTube video processing with full PMOVES.AI service integration.

## Features

- **Video Ingestion** - Send YouTube videos to PMOVES.YT for transcription and indexing
- **Knowledge Search** - Query Hi-RAG v2 hybrid retrieval (vector + graph + full-text)
- **AI Chat** - Ask questions via TensorZero LLM gateway
- **GPU Management** - Monitor VRAM, temperature, loaded models; optimize on demand
- **Voice Synthesis** - Text-to-speech via Flute Gateway
- **Agent Orchestration** - Execute MCP commands, submit tasks to Agent Zero runtime, view job logs
- **CHIT Pipeline** - Full demo_run orchestration (YT -> Hi-RAG -> Neo4j -> CGP -> decode -> calibration)
- **Shape Visualization** - Browse recent CGP shapes, view SVG constellation maps
- **Mesh Monitoring** - Service mesh health via Prometheus

## Install (Developer Mode)

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `pmoves/chrome-extension/` directory
5. The PMOVES.AI icon appears in the toolbar

## Service Endpoints

| Service | Default Port | Purpose |
|---------|-------------|---------|
| TensorZero | 3030 | LLM gateway (chat, embeddings) |
| GPU Orchestrator | 8200 | GPU/VRAM management |
| Hi-RAG v2 | 8086 | Hybrid RAG knowledge search |
| PMOVES.YT | 8077 | YouTube video ingestion |
| Agent Zero | 8080 | MCP agent orchestration |
| Flute Gateway | 8055 | Voice synthesis (TTS) |
| Prometheus | 9090 | Metrics and mesh agent status |
| Gateway (CHIT) | 8085 | CHIT Geometry Bus, shape visualization |

All endpoints are configurable in the extension's **Settings** page.

## Configuration

Click the extension icon > **Settings** (or right-click icon > Options):

- **Service Endpoints** - Customize URLs for each service
- **Authentication** - Agent Zero token, Flute API key
- **Features** - Toggle floating button, thumbnail buttons, notifications
- **Diagnostics** - Test all service connections with latency
- **Agent Zero Details** - Health check (`/healthz`), list MCP commands (`/mcp/commands`)
- **CHIT Geometry** - Recent shapes with SVG links, recent NATS events

## Usage

### On YouTube

- **Floating button** (bottom-right) opens an action menu:
  - Process current video
  - Search knowledge base (Hi-RAG)
  - Summarize with AI (TensorZero)
  - Read aloud (Flute TTS)
  - Process all videos on page
  - Monitor channel
- **Thumbnail buttons** appear on hover over video cards
- **Right-click context menus** on videos, channels, playlists

### Popup Dashboard

Click the toolbar icon to see:
- Health status grid for all 8 services
- GPU panel with VRAM bar, temperature, utilization
- Quick action inputs for ingestion, search, chat, TTS
- Agent Tasks: submit tasks to Agent Zero runtime (synchronous response)
- CHIT Pipeline: run full YT->CGP pipeline, browse recent shapes with SVG links
- Recent processing activity

## Architecture

```
background.js     Service worker: config, health polling, message routing
content.js        YouTube page injection: buttons, menus, overlays
lib/pmoves-api.js Shared API client for all 8 PMOVES.AI services
lib/constants.js  Default config, service URLs, health endpoints
popup/            Dashboard: health grid, GPU panel, quick actions
options/          Settings: endpoints, auth, features, diagnostics
```

The extension uses Chrome Manifest V3 with ES modules. The service worker (`background.js`) acts as the central message router between the popup, content script, and PMOVES.AI services.

## Integration Overview

The extension communicates **bidirectionally** with 8 PMOVES.AI services:

- **Outbound:** Content script and popup send `chrome.runtime.sendMessage()` to the background service worker, which proxies all API calls via `lib/pmoves-api.js`. This includes video ingestion, knowledge queries, LLM chat, GPU management, TTS synthesis, agent tasks, and CHIT pipeline operations.
- **Inbound:** The extension is **poll-only** — health status is refreshed every 30s via `chrome.alarms`, and GPU metrics update on the same interval. There are no WebSocket or NATS subscriptions.

For complete API reference, message protocol, and authentication details, see [`.claude/context/chrome-extension.md`](../../.claude/context/chrome-extension.md).

## Development

### Mock Server

```bash
cd pmoves/chrome-extension
node test/mock-server.js
```

Simulates all 8 service endpoints on their default ports for local development without the full Docker stack.

### Testing

1. Load the extension in developer mode (see Install above)
2. Run the mock server for offline testing
3. Open YouTube and verify floating button, thumbnail buttons, and context menus

### Adding New Service Integrations

Five-file checklist:

1. `lib/constants.js` — Add to `DEFAULT_SERVICES` and `HEALTH_ENDPOINTS`
2. `lib/pmoves-api.js` — Add API client module
3. `background.js` — Add `case` entries to `handleMessage()`
4. `manifest.json` — Add port to `host_permissions`
5. UI files (popup/options) — Add relevant controls

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All services show red | Docker not running | Run `docker compose --profile agents --profile workers up -d` |
| Video ingestion stuck at "queued" | PMOVES.YT down | Check `docker logs pmoves-yt`, verify port 8077 |
| AI chat/summary fails | TensorZero unreachable | Check `http://localhost:3030/healthz`, verify API keys |
| TTS not working | Flute Gateway down or no API key | Check port 8055, add Flute API key in Settings |
| No floating button on YouTube | Feature toggle off or page not reloaded | Enable in Settings > Features, reload the YouTube page |
| Toolbar badge shows "?" | Extension can't reach services | Check Docker, network, and firewall settings |
| Knowledge search returns nothing | No content ingested yet | Ingest videos first — the knowledge base starts empty |

**Checking service logs:**

```bash
# Individual service
docker logs <container-name>

# All services
docker compose logs -f --tail=50
```

## FAQ

**Can I use this without PMOVES.AI running?**
No — the extension is a frontend for PMOVES.AI Docker services. Without them, all features will show errors.

**Does it work on non-YouTube pages?**
The popup dashboard (health, chat, search, TTS, agent tasks, CHIT) works on any page. YouTube-specific features (floating button, thumbnail buttons) only appear on youtube.com.

**How do I update the extension?**
Pull the latest PMOVES.AI code, then go to `chrome://extensions` and click the refresh icon on the PMOVES.AI extension card.

**Where is my data stored?**
Settings and history use `chrome.storage.local` — local to your browser, not synced or uploaded anywhere.

**What does "Optimize VRAM" do?**
Calls the GPU Orchestrator to unload idle models from GPU memory, freeing VRAM for other tasks.

## User Guide

For comprehensive usage instructions including detailed feature walkthroughs, see **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**.
