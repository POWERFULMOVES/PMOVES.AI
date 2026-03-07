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
lib/pmoves-api.js Shared API client for all 7 PMOVES.AI services
lib/constants.js  Default config, service URLs, health endpoints
popup/            Dashboard: health grid, GPU panel, quick actions
options/          Settings: endpoints, auth, features, diagnostics
```

The extension uses Chrome Manifest V3 with ES modules. The service worker (`background.js`) acts as the central message router between the popup, content script, and PMOVES.AI services.
