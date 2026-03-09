# PMOVES.AI Chrome Extension — User Guide

## Getting Started

### Prerequisites

- **Google Chrome** (version 88 or later)
- **PMOVES.AI services running** — the extension connects to local Docker services. Without them, all features will show errors or timeouts.

### Installation

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** using the toggle in the top-right corner
3. Click **Load unpacked**
4. Select the `pmoves/chrome-extension/` folder from your PMOVES.AI project
5. The PMOVES.AI icon appears in your toolbar — you're ready to go

### First Launch

Click the PMOVES.AI icon in the toolbar to open the **Dashboard**. The top row shows 8 colored dots — this is the **Health Grid**. If your services are running, dots will turn green within a few seconds.

**Badge colors on the toolbar icon:**

| Badge | Meaning |
|-------|---------|
| Green (no number) | All 8 services are healthy |
| Orange with number (e.g. 5/8) | Some services are down — the number shows how many are up |
| Red with "OFF" | All services are unreachable |
| Gray with "?" | Polling error — extension can't check services |

---

## Dashboard (Popup)

Click the toolbar icon to open the popup dashboard. It contains several sections:

### Health Grid

Eight colored dots representing service status:

| Dot | Service | What It Does |
|-----|---------|-------------|
| TensorZero | LLM Gateway | Routes AI chat and embedding requests |
| GPU | GPU Orchestrator | Manages VRAM, models, optimization |
| Hi-RAG | Knowledge Search | Hybrid retrieval (vector + graph + full-text) |
| YT | PMOVES.YT | YouTube video ingestion and transcription |
| Agent0 | Agent Zero | Multi-agent orchestration via MCP |
| Flute | Flute Gateway | Voice synthesis (text-to-speech) |
| Mesh | Prometheus | Service mesh health and metrics |
| CHIT | Gateway | CHIT Geometry Bus and shape visualization |

- **Green (glowing)** = healthy
- **Red** = service is down or unreachable
- **Gray** = status unknown (not yet polled)
- Latency is shown below each dot in milliseconds

### GPU Panel

- **VRAM bar**: shows current GPU memory usage as a percentage
  - Green = under 70%, Orange = 70-90%, Red = over 90%
- **Temp**: GPU temperature in Celsius
- **Util**: GPU utilization percentage
- **Models**: number of currently loaded models
- **Optimize VRAM** button: triggers GPU memory optimization (unloads unused models)

### Quick Actions

Four input fields for common tasks:

1. **YouTube Ingest**: Paste a YouTube URL and click **Ingest** to queue it for transcription and indexing
2. **RAG Search**: Type a question and click **Search** to query the knowledge base via Hi-RAG v2
3. **Chat with AI**: Type any question and click **Ask** to get an AI response via TensorZero
4. **Text-to-Speech**: Type text and click **Speak** to synthesize speech via Flute Gateway

Results appear in a panel below the inputs. Press **Enter** in any field as a shortcut for the corresponding button.

### Agent Tasks

Submit free-form tasks to Agent Zero. Type a task description and click **Run**. Agent Zero will process the task using its MCP tools and return a response. This may take up to several minutes for complex tasks.

### CHIT Pipeline

Two inputs for CHIT Geometry operations:

1. **Pipeline**: Paste a YouTube URL and click **Pipeline** to run the full CHIT analysis (ingest -> Hi-RAG -> Neo4j -> CGP -> decode -> calibration). Results show the shape ID, constellations, and calibration metrics.
2. **Decode**: Enter comma-separated constellation IDs and click **Decode** to retrieve decoded items from the CHIT geometry bus.

Below these inputs, **recent shapes** are listed with clickable **SVG** links to view constellation maps.

### Recent Activity

Shows the last 5 processing jobs with status badges:

- **processing** (blue) — currently being worked on
- **completed** (green) — finished successfully
- **failed** (red) — encountered an error
- **queued** (orange) — waiting to be processed

### Refresh

Click the **refresh button** (circular arrow) in the header to manually update all sections.

---

## YouTube Features

These features appear when you visit YouTube pages.

### Floating Action Button

A circular purple button appears in the bottom-right corner of YouTube pages. Click it to open a menu with 8 actions:

| Action | What It Does |
|--------|-------------|
| Process Current Video | Sends the current video URL to PMOVES.YT for ingestion |
| Search Knowledge (Hi-RAG) | Opens a search overlay to query the knowledge base |
| Summarize with AI | Sends the video title and description to TensorZero for an AI summary |
| Read Aloud (TTS) | Sends the video title to Flute Gateway for speech synthesis |
| Process All on Page | Queues every video link on the current page for ingestion |
| Monitor Channel | Sends the current channel URL for ongoing monitoring |
| Processing History | Opens a modal showing all past processing jobs |
| Settings | Opens the extension settings page |

The button also displays a **GPU badge** — a small colored overlay showing current GPU utilization:
- Green = under 70%
- Orange = 70-90%
- Red = over 90%

### Thumbnail Buttons

When you hover over any video thumbnail on YouTube (homepage, search results, sidebar), a small circular PMOVES.AI icon appears in the top-right corner. Click it to immediately queue that video for processing.

### Right-Click Context Menus

Right-click on YouTube pages for additional options:
- **Process Video** — on video links
- **Monitor Channel** — on channel pages
- **Process Playlist** — on playlist pages

### Search Overlay

When you select "Search Knowledge" from the floating menu, a dark overlay appears with a search input. Type your query, press Enter or click Search, and results from Hi-RAG appear with relevance scores.

Press **Escape** to close any overlay or modal.

---

## Settings (Options Page)

Access settings by clicking **Settings** in the popup footer, or right-click the toolbar icon and select **Options**.

### Service Endpoints

Each of the 8 services has a URL field. Default values point to `localhost` at standard ports. Change these only if you've configured services on different ports or hosts.

Each field has a **Test** button to verify connectivity.

### Authentication

- **Agent Zero Bearer Token**: Required for agent task submission. Get this from your Agent Zero configuration (`AGENTZERO_API_TOKEN` in your `.env`).
- **Flute Gateway API Key**: Optional. Required only if your Flute Gateway has authentication enabled. Check your Flute `.env` for `FLUTE_API_KEY`.

### Feature Toggles

| Toggle | Default | What It Controls |
|--------|---------|-----------------|
| Auto-process videos on page load | Off | Automatically queue videos when you visit a YouTube page |
| Show floating action button | On | The purple circle button on YouTube pages |
| Show process buttons on thumbnails | On | PMOVES.AI icons on video thumbnail hover |
| Show desktop notifications | On | Chrome notifications for processing events |

**Health poll interval**: How often (in seconds) the extension checks service health. Default is 30 seconds. Range: 10-300.

### Diagnostics

- **Test All Services**: Runs health checks on all 8 services and displays a table with status, latency, and error details.
- **Agent Zero Health**: Fetches detailed health info from Agent Zero's `/healthz` endpoint.
- **MCP Commands**: Lists all available MCP commands from Agent Zero.
- **Recent Shapes**: Shows recent CHIT geometry shapes with SVG links.
- **Recent Events**: Shows recent events from the CHIT geometry bus.

---

## Troubleshooting

### All services show red

Your PMOVES.AI Docker services aren't running.

1. Check Docker: `docker ps` — are containers running?
2. Start services: `docker compose --profile agents --profile workers up -d`
3. Click refresh in the popup after services start

### Video ingestion stuck at "queued"

The PMOVES.YT service may be busy or down.

1. Check PMOVES.YT health: visit `http://localhost:8077/healthz`
2. Check Docker logs: `docker logs pmoves-yt`
3. Verify port 8077 is not blocked by another application

### AI summary or chat fails

TensorZero gateway may be unreachable.

1. Check TensorZero: visit `http://localhost:3030/healthz`
2. Verify your LLM API keys are configured in TensorZero's config
3. Check TensorZero UI at `http://localhost:4000` for error details

### TTS not working

1. Verify Flute Gateway is running: `http://localhost:8055/healthz`
2. If authentication is enabled, add your Flute API key in Settings
3. Check Docker logs: `docker logs flute-gateway`

### No floating button on YouTube

1. Check that "Show floating action button" is enabled in Settings
2. Reload the YouTube page (the extension injects on page load)
3. Check `chrome://extensions` — ensure the extension is enabled and not errored

### Badge shows "?"

The extension can't reach any service to check health.

1. Verify Docker is running
2. Check that no firewall is blocking localhost connections
3. Try clicking refresh in the popup

### Knowledge search returns no results

1. Verify Hi-RAG is healthy (green dot in Health Grid)
2. Ensure you've ingested content first — the knowledge base starts empty
3. Check that Qdrant, Neo4j, and Meilisearch containers are running

---

## FAQ

**Can I use this without PMOVES.AI running?**
No. The extension is a frontend for PMOVES.AI services. Without them running locally (via Docker), all features will fail. The popup will still open, but all dots will be red.

**Does it work on non-YouTube pages?**
The popup dashboard works on any page — you can use Quick Actions, Agent Tasks, and CHIT Pipeline everywhere. The YouTube-specific features (floating button, thumbnail buttons, context menus) only appear on youtube.com.

**How do I update the extension?**
Pull the latest PMOVES.AI code, then go to `chrome://extensions` and click the refresh icon on the PMOVES.AI card.

**Where is my data stored?**
Settings and processing history are stored in `chrome.storage.local` — local to your browser, not synced or sent anywhere. All API calls go to your local PMOVES.AI services.

**Can I change the keyboard shortcuts?**
The extension doesn't define custom keyboard shortcuts. You can set one in Chrome at `chrome://extensions/shortcuts` to open the popup.

**What does "Optimize VRAM" do?**
It calls the GPU Orchestrator to unload idle models from GPU memory, freeing VRAM for other tasks. Use it when VRAM usage is high and you want to reclaim memory.
