# PMOVES Pinokio Example Manifests

> **Last Updated:** 2026-03-22  
> **Related:** [PINOKIO_PACKAGING_GUIDE.md](./PINOKIO_PACKAGING_GUIDE.md)

This document provides complete, copy-paste ready Pinokio manifest examples for various PMOVES agent types.

---

## Table of Contents

1. [Agent Zero - Full Agent Runtime](#example-1-agent-zero---full-agent-runtime)
2. [Hi-RAG v2 - API/Worker Service](#example-2-hi-rag-v2---apiworker-service)
3. [Ultimate-TTS - GPU Media Service](#example-3-ultimate-tts---gpu-media-service)
4. [PMOVES Services - Multi-Profile Stack](#example-4-pmoves-services---multi-profile-stack)
5. [Crush - UI-Only App](#example-5-crush---ui-only-app)
6. [Cipher Beats Analyst - CLI Tool](#example-6-cipher-beats-analyst---cli-tool)

---

## Example 1: Agent Zero - Full Agent Runtime

**Agent Type:** Tier 6+2 (Agent+API)  
**GPU:** Optional  
**Port:** 8080

### Folder Structure

```
pmoves-agent-zero/
├── pinokio/
│   ├── install.js
│   ├── start.js
│   ├── reset.js
│   ├── update.js
│   └── pinokio.js
├── pinokio.json
├── README.md
└── icon.png
```

### pinokio.json

```json
{
  "version": "1",
  "title": "PMOVES Agent Zero",
  "description": "Primary L1 orchestrator with embedded agent runtime and MCP API. Autonomous task execution with memory persistence, multi-LLM support, and 100+ tools via MCP discovery.",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": "optional",
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero",
  "homepage": "https://pmoves.ai",
  "pmoves_version": "1.4.0",
  "keywords": ["agent", "orchestrator", "mcp", "llm", "pmoves", "autonomous"]
}
```

### pinokio/pinokio.js

```javascript
// pinokio/pinokio.js
// Dynamic menu for PMOVES Agent Zero

const installed = info.exists("app/.installed")
const running = info.running("start.js")
const url = info.local("start.js", "url")

module.exports = {
  run: !installed ? [
    { method: "script", params: { uri: "install.js" } }
  ] : [],
  menu: [
    {
      id: "install",
      title: "Install",
      description: "Clone and install Agent Zero",
      script: "install.js",
      default: !installed
    },
    {
      id: "start",
      title: "Start Agent",
      description: "Launch Agent Zero runtime",
      script: "start.js",
      running: running,
      default: installed && !running
    },
    {
      id: "api",
      title: "Open API (Swagger)",
      href: url ? `${url}/docs` : "http://localhost:8080/docs",
      default: running
    },
    {
      id: "mcp",
      title: "MCP Endpoint",
      href: url ? `${url}/mcp` : "http://localhost:8080/mcp",
      disabled: !running
    },
    {
      id: "health",
      title: "Health Check",
      href: url ? `${url}/healthz` : "http://localhost:8080/healthz",
      disabled: !running
    },
    // Divider
    { type: "divider", title: "Maintenance" },
    {
      id: "update",
      title: "Update",
      description: "Pull latest changes",
      script: "update.js",
      disabled: !installed
    },
    {
      id: "reset",
      title: "Reset",
      description: "Clean installation",
      script: "reset.js",
      disabled: running
    }
  ]
}
```

### pinokio/install.js

```javascript
// pinokio/install.js
// Installation script for PMOVES Agent Zero

module.exports = {
  run: [
    // Clean previous installation
    {
      method: "fs.rm",
      params: { path: "app" }
    },
    
    // Clone repository
    {
      method: "git.clone",
      params: {
        url: "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero",
        path: "app",
        branch: "main"
      }
    },
    
    // Install Python dependencies
    {
      method: "shell.run",
      params: {
        path: "app",
        message: platform === "win32"
          ? "pip install -r requirements.txt"
          : "pip3 install -r requirements.txt"
      }
    },
    
    // Create example environment file
    {
      method: "fs.write",
      params: {
        path: "app/.env.example",
        text: `
# =============================================================================
# PMOVES Agent Zero Configuration
# =============================================================================
# Copy this file to .env and fill in your values

# -----------------------------------------------------------------------------
# LLM Providers (at least one required)
# -----------------------------------------------------------------------------
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_API_KEY=xxx

# -----------------------------------------------------------------------------
# Supabase (required for persistence)
# -----------------------------------------------------------------------------
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJxxx

# -----------------------------------------------------------------------------
# NATS Event Bus (optional)
# -----------------------------------------------------------------------------
NATS_URL=nats://localhost:4222

# -----------------------------------------------------------------------------
# MCP Servers (optional - for tool discovery)
# -----------------------------------------------------------------------------
# Format: name: "mcp://transport?params"
A0_MCP_SERVERS=
  archon: "mcp://http?endpoint=http://localhost:8091";
  neo4j: "mcp://neo4j?url=bolt://localhost:7687&user=neo4j&password=xxx";
  filesystem: "mcp://filesystem?roots=/data";

# -----------------------------------------------------------------------------
# Server Configuration
# -----------------------------------------------------------------------------
HOST=0.0.0.0
PORT=8080
        `.trim()
      }
    },
    
    // Create installation marker
    {
      method: "fs.write",
      params: {
        path: "app/.installed",
        text: new Date().toISOString()
      }
    },
    
    // Notify user
    {
      method: "notify",
      params: {
        title: "Agent Zero Installed",
        message: "Copy app/.env.example to app/.env and configure before starting."
      }
    }
  ]
}
```

### pinokio/start.js

```javascript
// pinokio/start.js
// Launch script for PMOVES Agent Zero

module.exports = {
  run: [
    // Check if .env exists
    {
      method: "fs.exists",
      params: { path: "app/.env" },
      returns: "env_exists"
    },
    
    // Warn if no .env
    {
      method: "notify",
      params: {
        title: "Configuration Required",
        message: "Please copy app/.env.example to app/.env and configure before starting.",
        type: "warning"
      },
      when: !input.env_exists
    },
    
    // Start the agent
    {
      method: "shell.run",
      params: {
        path: "app",
        message: platform === "win32"
          ? "python main.py"
          : "python3 main.py",
        env: {
          HOST: "0.0.0.0",
          PORT: "8080",
          PYTHONUNBUFFERED: "1"
        },
        on: [
          {
            // Capture the URL from startup output
            event: "/Uvicorn running on (http:\\/\\/[0-9.:]+)/",
            done: true
          }
        ]
      }
    },
    
    // Store the URL for menu access
    {
      method: "local.set",
      params: {
        url: input.event[1],
        started: new Date().toISOString()
      }
    },
    
    // Notify user
    {
      method: "notify",
      params: {
        title: "Agent Zero Started",
        message: `Running at ${input.event[1]}\nAPI Docs: ${input.event[1]}/docs`
      }
    }
  ]
}
```

### pinokio/reset.js

```javascript
// pinokio/reset.js
// Reset script for PMOVES Agent Zero

module.exports = {
  run: [
    // Remove Python cache and dependencies
    {
      method: "shell.run",
      params: {
        path: "app",
        message: platform === "win32"
          ? "rmdir /s /q __pycache__ 2>nul & del /f .installed 2>nul"
          : "rm -rf __pycache__ .installed",
        throws: false
      }
    },
    
    // Remove environment file
    {
      method: "fs.rm",
      params: { path: "app/.env" }
    },
    
    // Remove installation marker
    {
      method: "fs.rm",
      params: { path: "app/.installed" }
    },
    
    // Notify user
    {
      method: "notify",
      params: {
        title: "Agent Zero Reset",
        message: "Installation cleaned. Run Install to set up again."
      }
    }
  ]
}
```

### pinokio/update.js

```javascript
// pinokio/update.js
// Update script for PMOVES Agent Zero

module.exports = {
  run: [
    // Pull latest changes
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "git pull origin main"
      }
    },
    
    // Update dependencies
    {
      method: "shell.run",
      params: {
        path: "app",
        message: platform === "win32"
          ? "pip install -r requirements.txt --upgrade"
          : "pip3 install -r requirements.txt --upgrade"
      }
    },
    
    // Update installation marker
    {
      method: "fs.write",
      params: {
        path: "app/.installed",
        text: new Date().toISOString()
      }
    },
    
    // Notify user
    {
      method: "notify",
      params: {
        title: "Agent Zero Updated",
        message: "Latest changes pulled and dependencies updated."
      }
    }
  ]
}
```

---

## Example 2: Hi-RAG v2 - API/Worker Service

**Agent Type:** Tier 4+1 (Worker+Data)  
**GPU:** Optional (CPU on 8086, GPU on 8087)  
**Ports:** 8086 (CPU), 8087 (GPU)

### Folder Structure

```
pmoves-hirag/
├── pinokio/
│   ├── install.js
│   ├── start-cpu.js
│   ├── start-gpu.js
│   ├── reset.js
│   └── pinokio.js
├── pinokio.json
├── README.md
└── icon.png
```

### pinokio.json

```json
{
  "version": "1",
  "title": "PMOVES Hi-RAG v2",
  "description": "Hybrid RAG gateway combining Qdrant vector search + Neo4j knowledge graphs + Meilisearch full-text search with optional GPU cross-encoder reranking.",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": "optional",
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-HiRAG",
  "homepage": "https://pmoves.ai",
  "keywords": ["rag", "search", "vector", "neo4j", "qdrant", "gpu", "reranker"]
}
```

### pinokio/pinokio.js

```javascript
// pinokio/pinokio.js
// Dynamic menu for Hi-RAG v2

const installed = info.exists("app/.installed")
const cpuRunning = info.running("start-cpu.js")
const gpuRunning = info.running("start-gpu.js")
const cpuUrl = info.local("start-cpu.js", "url")
const gpuUrl = info.local("start-gpu.js", "url")
const hasGpu = gpu === "nvidia"

module.exports = {
  menu: [
    {
      id: "install",
      title: "Install",
      description: "Clone and install Hi-RAG v2",
      script: "install.js",
      default: !installed
    },
    // Divider
    { type: "divider", title: "Start Service" },
    {
      id: "start-cpu",
      title: "Start CPU Instance",
      description: "Launch CPU-only instance on port 8086",
      script: "start-cpu.js",
      running: cpuRunning,
      default: installed && !cpuRunning && !gpuRunning
    },
    {
      id: "start-gpu",
      title: "Start GPU Instance",
      description: "Launch GPU-accelerated instance on port 8087 (requires NVIDIA)",
      script: "start-gpu.js",
      running: gpuRunning,
      disabled: !hasGpu,
      default: installed && !cpuRunning && !gpuRunning && hasGpu
    },
    // Divider
    { type: "divider", title: "Endpoints" },
    {
      id: "cpu-api",
      title: "CPU API",
      description: "Hi-RAG CPU instance stats",
      href: cpuUrl || "http://localhost:8086/hirag/admin/stats",
      disabled: !cpuRunning
    },
    {
      id: "gpu-api",
      title: "GPU API",
      description: "Hi-RAG GPU instance stats with reranking",
      href: gpuUrl || "http://localhost:8087/hirag/admin/stats",
      disabled: !gpuRunning
    },
    {
      id: "cpu-docs",
      title: "CPU Docs",
      href: cpuUrl ? `${cpuUrl}/docs` : "http://localhost:8086/docs",
      disabled: !cpuRunning
    },
    {
      id: "gpu-docs",
      title: "GPU Docs",
      href: gpuUrl ? `${gpuUrl}/docs` : "http://localhost:8087/docs",
      disabled: !gpuRunning
    },
    // Divider
    { type: "divider", title: "Maintenance" },
    {
      id: "reset",
      title: "Reset",
      script: "reset.js"
    }
  ]
}
```

### pinokio/start-cpu.js

```javascript
// pinokio/start-cpu.js
// Launch CPU instance

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: platform === "win32"
          ? "python -m hirag.gateway --host 0.0.0.0 --port 8086"
          : "python3 -m hirag.gateway --host 0.0.0.0 --port 8086",
        env: {
          EMBEDDING_MODEL: "BAAI/bge-m3",
          PYTHONUNBUFFERED: "1"
        },
        on: [
          {
            event: "/Uvicorn running on (http:\\/\\/[0-9.:]+)/",
            done: true
          }
        ]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1],
        mode: "cpu",
        started: new Date().toISOString()
      }
    },
    {
      method: "notify",
      params: {
        title: "Hi-RAG CPU Started",
        message: `CPU instance running at ${input.event[1]}\nEmbedding model: BAAI/bge-m3`
      }
    }
  ]
}
```

### pinokio/start-gpu.js

```javascript
// pinokio/start-gpu.js
// Launch GPU instance with cross-encoder reranking

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: platform === "win32"
          ? "python -m hirag.gateway --host 0.0.0.0 --port 8087 --gpu"
          : "python3 -m hirag.gateway --host 0.0.0.0 --port 8087 --gpu",
        env: {
          CUDA_VISIBLE_DEVICES: "0",
          RERANKER_MODEL: "BAAI/bge-reranker-v2-m3",
          EMBEDDING_MODEL: "BAAI/bge-m3",
          PYTHONUNBUFFERED: "1"
        },
        on: [
          {
            event: "/Uvicorn running on (http:\\/\\/[0-9.:]+)/",
            done: true
          }
        ]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1],
        mode: "gpu",
        reranker: "BAAI/bge-reranker-v2-m3",
        started: new Date().toISOString()
      }
    },
    {
      method: "notify",
      params: {
        title: "Hi-RAG GPU Started",
        message: `GPU instance running at ${input.event[1]}\nReranking enabled with BGE-v2-m3`
      }
    }
  ]
}
```

---

## Example 3: Ultimate-TTS - GPU Media Service

**Agent Type:** Tier 5+3 (Media+LLM)  
**GPU:** Recommended  
**Port:** 7861

### pinokio.json

```json
{
  "version": "1",
  "title": "PMOVES Ultimate TTS Studio",
  "description": "Multi-engine TTS studio with 14 voice engines including Coqui XTTS, StyleTTS2, VITS, RVC, and more. GPU recommended for real-time synthesis.",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": "recommended",
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-Ultimate-TTS-Studio",
  "homepage": "https://pmoves.ai",
  "keywords": ["tts", "voice", "synthesis", "audio", "gpu", "gradio", "coqui", "styletts"]
}
```

### pinokio/pinokio.js

```javascript
// pinokio/pinokio.js
// Dynamic menu for Ultimate TTS Studio

const installed = info.exists("app/.installed")
const running = info.running("start.js")
const url = info.local("start.js", "url")
const mode = info.local("start.js", "mode")

module.exports = {
  menu: [
    {
      id: "install",
      title: "Install",
      description: "Clone and install TTS Studio (may take several minutes)",
      script: "install.js",
      default: !installed
    },
    {
      id: "start",
      title: running ? "Stop TTS Studio" : "Start TTS Studio",
      description: mode 
        ? `Running in ${mode.toUpperCase()} mode`
        : "Launch TTS Studio (auto-detects GPU)",
      script: "start.js",
      running: running,
      default: installed && !running
    },
    {
      id: "open",
      title: "Open Gradio UI",
      href: url || "http://localhost:7861",
      default: running
    },
    {
      id: "api",
      title: "API Docs",
      href: url ? `${url}/gradio_api` : "http://localhost:7861/gradio_api",
      disabled: !running
    },
    // Divider
    { type: "divider", title: "Maintenance" },
    {
      id: "clear-cache",
      title: "Clear Cache",
      description: "Remove Gradio temp files",
      script: "clear-cache.js",
      disabled: !installed
    },
    {
      id: "reset",
      title: "Reset",
      script: "reset.js"
    }
  ]
}
```

### pinokio/start.js

```javascript
// pinokio/start.js
// Launch Ultimate TTS Studio with Gradio UI

const hasGpu = gpu === "nvidia"

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: hasGpu
          ? "python launch.py --gpu --port 7861"
          : "python launch.py --cpu --port 7861",
        env: {
          GRADIO_SERVER_NAME: "0.0.0.0",
          GRADIO_SERVER_PORT: "7861",
          PYTHONUNBUFFERED: "1"
        },
        on: [
          {
            event: "/Running on (http:\\/\\/[0-9.:]+)/",
            done: true
          }
        ]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1],
        mode: hasGpu ? "gpu" : "cpu",
        engines: 14,
        started: new Date().toISOString()
      }
    },
    {
      method: "notify",
      params: {
        title: "Ultimate TTS Studio Started",
        message: `Running at ${input.event[1]}\n14 TTS engines available (${hasGpu ? "GPU" : "CPU"} mode)`
      }
    }
  ]
}
```

---

## Example 4: PMOVES Services - Multi-Profile Stack

**Type:** Multi-service Docker Compose orchestration  
**Profiles:** data, workers, agents, gpu

### pinokio/pinokio.js

```javascript
// pinokio/pinokio.js
// Multi-profile launcher for PMOVES core services

const installed = info.exists(".installed")
const dataRunning = info.running("start-data.js")
const workersRunning = info.running("start-workers.js")
const agentsRunning = info.running("start-agents.js")
const gpuRunning = info.running("start-gpu.js")

const anyRunning = dataRunning || workersRunning || agentsRunning || gpuRunning
const allRunning = dataRunning && workersRunning && agentsRunning && gpuRunning
const hasGpu = gpu === "nvidia"

module.exports = {
  menu: [
    {
      id: "install",
      title: "Install Dependencies",
      description: "Clone submodules and install all dependencies",
      script: "install.js",
      default: !installed
    },
    // Divider
    { type: "divider", title: "Service Profiles" },
    {
      id: "start-data",
      title: dataRunning ? "✓ Data Layer Running" : "Start Data Layer",
      description: "NATS :4222, Qdrant :6333, Neo4j :7474, Meilisearch :7700",
      script: "start-data.js",
      running: dataRunning
    },
    {
      id: "start-workers",
      title: workersRunning ? "✓ Workers Running" : "Start Workers",
      description: "Hi-RAG :8086, Extract :8083, PDF Ingest :8092, Channel Monitor :8097",
      script: "start-workers.js",
      running: workersRunning
    },
    {
      id: "start-agents",
      title: agentsRunning ? "✓ Agents Running" : "Start Agents",
      description: "Agent Zero :8080, Archon :8091, SupaSerch :8099",
      script: "start-agents.js",
      running: agentsRunning
    },
    {
      id: "start-gpu",
      title: gpuRunning ? "✓ GPU Services Running" : "Start GPU Services",
      description: "Ultimate-TTS :7861, Media-Video :8079, FFmpeg-Whisper :8078",
      script: "start-gpu.js",
      running: gpuRunning,
      disabled: !hasGpu
    },
    // Divider
    { type: "divider", title: "Quick Actions" },
    {
      id: "start-all",
      title: "Start All Services",
      description: "Launch all profiles at once",
      script: "start-all.js",
      disabled: anyRunning
    },
    {
      id: "stop-all",
      title: "Stop All Services",
      description: "Stop all running profiles",
      script: "stop-all.js",
      disabled: !anyRunning
    },
    // Divider
    { type: "divider", title: "Status & Logs" },
    {
      id: "status",
      title: "Service Status",
      description: "Check health of all services",
      script: "status.js"
    },
    {
      id: "logs",
      title: "View Logs",
      href: "logs/"
    }
  ]
}
```

### pinokio/start-data.js

```javascript
// pinokio/start-data.js
// Start data layer services via Docker Compose

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../..",  // PMOVES.AI root with docker-compose.yml
        message: "docker compose --profile data up -d",
        on: [
          {
            event: "/Container (.*) Started/",
            done: false
          },
          {
            event: "/Network pmoves-net (created|already exists)/",
            done: true
          }
        ]
      }
    },
    {
      method: "local.set",
      params: {
        profile: "data",
        services: ["nats", "qdrant", "neo4j", "meilisearch"],
        started: new Date().toISOString()
      }
    },
    {
      method: "notify",
      params: {
        title: "Data Layer Started",
        message: "NATS :4222\nQdrant :6333\nNeo4j :7474\nMeilisearch :7700"
      }
    }
  ]
}
```

### pinokio/stop-all.js

```javascript
// pinokio/stop-all.js
// Stop all PMOVES services

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../..",
        message: "docker compose --profile data --profile workers --profile agents --profile gpu down",
        on: [
          {
            event: "/Container (.*) Stopped/",
            done: false
          },
          {
            event: "/Network pmoves-net removed/",
            done: true
          }
        ]
      }
    },
    {
      method: "notify",
      params: {
        title: "All Services Stopped",
        message: "All PMOVES service profiles have been stopped."
      }
    }
  ]
}
```

### pinokio/status.js

```javascript
// pinokio/status.js
// Check health of all PMOVES services

const services = [
  { name: "NATS", url: "http://localhost:8222/varz", port: 4222 },
  { name: "Qdrant", url: "http://localhost:6333/healthz", port: 6333 },
  { name: "Neo4j", url: "http://localhost:7474", port: 7474 },
  { name: "Meilisearch", url: "http://localhost:7700/health", port: 7700 },
  { name: "Agent Zero", url: "http://localhost:8080/healthz", port: 8080 },
  { name: "Archon", url: "http://localhost:8091/healthz", port: 8091 },
  { name: "Hi-RAG CPU", url: "http://localhost:8086/healthz", port: 8086 },
  { name: "Hi-RAG GPU", url: "http://localhost:8087/healthz", port: 8087 },
  { name: "Ultimate TTS", url: "http://localhost:7861/gradio_api/info", port: 7861 }
]

const results = []

module.exports = {
  run: [
    // Check each service
    ...services.map(service => ({
      method: "request",
      params: {
        uri: service.url,
        method: "GET",
        timeout: 3000
      },
      returns: `${service.name}_status`,
      error: `${service.name}_error`
    })),
    
    // Build status report
    {
      method: "notify",
      params: {
        title: "PMOVES Service Status",
        message: services.map(service => {
          const status = input[`${service.name}_status`]
          const error = input[`${service.name}_error`]
          const icon = status?.status === 200 || status ? "✅" : "❌"
          return `${icon} ${service.name} (:${service.port})`
        }).join("\n")
      }
    }
  ]
}
```

---

## Example 5: Crush - UI-Only App

**Agent Type:** Tier 7+6 (UI+Agent)  
**GPU:** Not required  
**Port:** 3000

### pinokio.json

```json
{
  "version": "1",
  "title": "PMOVES Crush",
  "description": "Terminal AI coding assistant — the gateway where model and user begin their journey. Web-based terminal interface with multi-model support.",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": false,
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-crush",
  "homepage": "https://pmoves.ai",
  "keywords": ["terminal", "coding", "assistant", "ui", "web"]
}
```

### pinokio/pinokio.js

```javascript
// pinokio/pinokio.js
// Dynamic menu for Crush terminal UI

const installed = info.exists("app/node_modules")
const running = info.running("start.js")
const url = info.local("start.js", "url")

module.exports = {
  menu: [
    {
      id: "install",
      title: "Install",
      description: "Clone and install Crush dependencies",
      script: "install.js",
      default: !installed
    },
    {
      id: "start",
      title: running ? "Stop Crush" : "Start Crush",
      description: "Launch the terminal UI",
      script: "start.js",
      running: running,
      default: installed && !running
    },
    {
      id: "open",
      title: "Open Terminal",
      href: url || "http://localhost:3000",
      default: running
    },
    // Divider
    { type: "divider", title: "Configuration" },
    {
      id: "config",
      title: "Edit Configuration",
      href: "app/.env"
    },
    // Divider
    { type: "divider", title: "Maintenance" },
    {
      id: "reset",
      title: "Reset",
      script: "reset.js"
    }
  ]
}
```

### pinokio/start.js

```javascript
// pinokio/start.js
// Launch Crush web terminal

module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "npm run dev",
        env: {
          PORT: "3000",
          NEXT_PUBLIC_AGENT_ZERO_URL: "http://localhost:8080",
          NEXT_PUBLIC_ARCHON_URL: "http://localhost:8091"
        },
        on: [
          {
            event: "/Local:\\s+(http:\\/\\/[0-9.:]+)/",
            done: true
          }
        ]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1],
        started: new Date().toISOString()
      }
    },
    {
      method: "notify",
      params: {
        title: "Crush Started",
        message: `Terminal ready at ${input.event[1]}`
      }
    }
  ]
}
```

---

## Example 6: Cipher Beats Analyst - CLI Tool

**Agent Type:** Tier 5+6 (Media+Agent)  
**Runtime:** CLI (no HTTP server)  
**Signature:** Gemini CLI driven

### pinokio.json

```json
{
  "version": "1",
  "title": "PMOVES Cipher Beats Analyst",
  "description": "Level 11 Cipher Gateway Specialist. Extracts sonic fingerprints via ffprobe/ffmpeg, clusters DARKXSIDE beats into named constellations, and generates M3U8 playlists.",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": false,
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-cipher-beats",
  "homepage": "https://pmoves.ai",
  "keywords": ["audio", "beats", "analysis", "ffmpeg", "cli", "playlist"]
}
```

### pinokio/pinokio.js

```javascript
// pinokio/pinokio.js
// Menu for Cipher Beats Analyst CLI tool

const installed = info.exists("app/.installed")

module.exports = {
  menu: [
    {
      id: "install",
      title: "Install",
      description: "Clone and install beats analyzer",
      script: "install.js",
      default: !installed
    },
    // Divider
    { type: "divider", title: "Analysis Tools" },
    {
      id: "analyze-folder",
      title: "Analyze Folder",
      description: "Select a folder and analyze all audio files",
      script: "analyze-folder.js"
    },
    {
      id: "analyze-file",
      title: "Analyze Single File",
      description: "Select and analyze a single audio file",
      script: "analyze-file.js"
    },
    {
      id: "cluster",
      title: "Cluster Beats",
      description: "Cluster analyzed beats into constellations",
      script: "cluster.js"
    },
    {
      id: "generate-playlist",
      title: "Generate Playlist",
      description: "Create M3U8 playlist from clusters",
      script: "generate-playlist.js"
    },
    // Divider
    { type: "divider", title: "Results" },
    {
      id: "view-results",
      title: "View Results",
      href: "app/output/"
    },
    // Divider
    { type: "divider", title: "Maintenance" },
    {
      id: "reset",
      title: "Reset",
      script: "reset.js"
    }
  ]
}
```

### pinokio/analyze-folder.js

```javascript
// pinokio/analyze-folder.js
// Analyze all audio files in a folder

module.exports = {
  run: [
    // Open file picker for folder selection
    {
      method: "shell.run",
      params: {
        message: "pterm filepicker --directory",
        returns: "folder_path"
      }
    },
    
    // Run analysis
    {
      method: "shell.run",
      params: {
        path: "app",
        message: `uv run python pmoves/tools/analyze_beats.py "${input.folder_path}" --output output/`,
        env: {
          PYTHONUNBUFFERED: "1"
        }
      }
    },
    
    // Notify user
    {
      method: "notify",
      params: {
        title: "Analysis Complete",
        message: `Analyzed audio files from ${input.folder_path}\nResults saved to app/output/`
      }
    }
  ]
}
```

---

## Summary

| Example | Agent Type | GPU | Key Features |
|---------|-----------|-----|--------------|
| Agent Zero | Agent+API | Optional | Full runtime, MCP, environment config |
| Hi-RAG v2 | Worker+Data | Optional | Dual-mode (CPU/GPU), port selection |
| Ultimate-TTS | Media+LLM | Recommended | Gradio UI, auto GPU detection |
| PMOVES Services | Multi-profile | Mixed | Docker Compose, health checks |
| Crush | UI+Agent | No | Next.js frontend, terminal UI |
| Cipher Beats | Media+Agent | No | CLI tool, file picker integration |

---

**Next Steps:**
- See [PINOKIO_PACKAGING_GUIDE.md](./PINOKIO_PACKAGING_GUIDE.md) for detailed API reference
- See [pbnj/pinokio/api/](../../../pbnj/pinokio/api/) for existing implementations
- See [CLAUDE.md](../../../CLAUDE.md) for Pinokio scripting rules
