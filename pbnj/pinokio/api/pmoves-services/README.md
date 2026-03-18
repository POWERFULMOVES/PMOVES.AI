# PMOVES Services

One-click control center for all PMOVES.AI Docker Compose services — agents, workers, monitoring, voice, and external integrations. 40+ microservices orchestrated via Docker Compose profiles.

## Quick Start

1. Click **Install** to bootstrap the environment (generates `.env` files)
2. Click **Start Core** to launch Agent Zero + workers
3. Open the **Agent Zero UI** at `http://localhost:8081`

## Service Profiles

| Profile | Script | What It Launches |
|---------|--------|-----------------|
| Core (Agents + Workers) | `start-core.js` | Agent Zero, Archon, Mesh Agent, Extract Worker, media analyzers |
| Monitoring | `start-monitoring.js` | Prometheus, Grafana, Loki, Promtail, cAdvisor |
| Voice | `start-voice.js` | Flute-Gateway, Ultimate-TTS-Studio, Cast, media pipeline |
| External | `start-external.js` | Wger, Firefly, Jellyfin (via `docker-compose.external.yml`) |

Additional scripts:

- **status.js** — Show running containers across all compose files
- **stop.js** — Gracefully stop all services (no volume deletion)
- **reset.js** — Stop all services AND delete volumes (full reset)
- **update.js** — `git pull` + submodule update + re-bootstrap env

## API Reference

### Agent Zero (Orchestrator)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `http://localhost:8080/healthz` | GET | Health check |
| `http://localhost:8080/mcp/command` | POST | MCP command API |
| `http://localhost:8081` | GET | Web UI |

**Curl**

```bash
# Health check
curl http://localhost:8080/healthz

# Send MCP command
curl -X POST http://localhost:8080/mcp/command \
  -H "Content-Type: application/json" \
  -d '{"command": "list_tools"}'
```

**Python**

```python
import requests

# Health check
r = requests.get("http://localhost:8080/healthz")
print(r.json())

# MCP command
r = requests.post("http://localhost:8080/mcp/command", json={"command": "list_tools"})
print(r.json())
```

**JavaScript**

```javascript
// Health check
const health = await fetch("http://localhost:8080/healthz").then(r => r.json());

// MCP command
const result = await fetch("http://localhost:8080/mcp/command", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ command: "list_tools" })
}).then(r => r.json());
```

### TensorZero (LLM Gateway) — Port 3030

**Curl**

```bash
# Chat completion
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}'

# Embeddings
curl -X POST http://localhost:3030/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma_embed_local", "input": "Text to embed"}'
```

**Python**

```python
import requests

# Chat completion
r = requests.post("http://localhost:3030/v1/chat/completions", json={
    "model": "claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "Hello"}]
})
print(r.json()["choices"][0]["message"]["content"])

# Embeddings
r = requests.post("http://localhost:3030/v1/embeddings", json={
    "model": "gemma_embed_local",
    "input": "Text to embed"
})
print(r.json()["data"][0]["embedding"][:5])
```

**JavaScript**

```javascript
// Chat completion
const chat = await fetch("http://localhost:3030/v1/chat/completions", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "claude-sonnet-4-5",
    messages: [{ role: "user", content: "Hello" }]
  })
}).then(r => r.json());

// Embeddings
const embed = await fetch("http://localhost:3030/v1/embeddings", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ model: "gemma_embed_local", input: "Text to embed" })
}).then(r => r.json());
```

### Hi-RAG v2 (Hybrid Search) — Port 8086

**Curl**

```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How does agent orchestration work?", "top_k": 10, "rerank": true}'
```

**Python**

```python
import requests

r = requests.post("http://localhost:8086/hirag/query", json={
    "query": "How does agent orchestration work?",
    "top_k": 10,
    "rerank": True
})
print(r.json())
```

**JavaScript**

```javascript
const results = await fetch("http://localhost:8086/hirag/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: "How does agent orchestration work?", top_k: 10, rerank: true })
}).then(r => r.json());
```

### Flute-Gateway (Voice Synthesis) — Port 8055

**Curl**

```bash
# Health check
curl http://localhost:8055/healthz

# Prosodic TTS
curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, welcome to PMOVES.", "voice": "default"}'
```

**Python**

```python
import requests

r = requests.post("http://localhost:8055/v1/voice/synthesize/prosodic", json={
    "text": "Hello, welcome to PMOVES.",
    "voice": "default"
})
# r.content contains audio bytes
with open("output.wav", "wb") as f:
    f.write(r.content)
```

**JavaScript**

```javascript
const response = await fetch("http://localhost:8055/v1/voice/synthesize/prosodic", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: "Hello, welcome to PMOVES.", voice: "default" })
});
const audioBlob = await response.blob();
```

### Monitoring

| Service | Port | URL |
|---------|------|-----|
| Grafana | 3000 | `http://localhost:3000` |
| Prometheus | 9090 | `http://localhost:9090` |
| Loki | 3100 | `http://localhost:3100` |

```bash
# Query Prometheus targets
curl http://localhost:9090/api/v1/query?query=up

# Check Grafana
curl http://localhost:3000/api/health
```

## Agent Hints

AI agents can use this launcher to:

- **Search knowledge** — Query Hi-RAG v2 at port 8086 for semantic + keyword + graph search
- **Speak text** — Synthesize speech via Flute-Gateway at port 8055
- **Chat with LLMs** — Route through TensorZero gateway at port 3030 (OpenAI-compatible)
- **Generate embeddings** — Create vector embeddings via TensorZero at port 3030
- **Check service health** — Run `status.js` or curl individual `/healthz` endpoints
- **Orchestrate agents** — Send MCP commands to Agent Zero at port 8080
