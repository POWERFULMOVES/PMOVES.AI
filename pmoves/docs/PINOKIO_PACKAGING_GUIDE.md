# PMOVES Agent Packaging Guide for Pinokio

> **Last Updated:** 2026-03-22  
> **Pinokio Version:** 7.x+  
> **PMOVES Taxonomy Version:** 1.4.0

This guide explains how to package PMOVES agents and services for deployment through [Pinokio](https://pinokio.computer), the AI app browser that enables one-click installation and execution of complex AI applications.

---

## Table of Contents

1. [Overview](#overview)
2. [Pinokio Architecture](#pinokio-architecture)
3. [PMOVES Agent Types & Pinokio Mapping](#pmoves-agent-types--pinokio-mapping)
4. [Folder Structure](#folder-structure)
5. [Required Files](#required-files)
6. [Script APIs](#script-apis)
7. [Packaging Patterns by Agent Type](#packaging-patterns-by-agent-type)
8. [Examples](#examples)
9. [Testing & Validation](#testing--validation)
10. [Distribution](#distribution)
11. [Troubleshooting](#troubleshooting)

---

## Overview

### What is Pinokio?

Pinokio is a browser-based AI engine that provides:
- **One-click installation** of complex AI applications
- **Cross-platform scripting** (Windows, macOS, Linux)
- **Dynamic UI generation** through JavaScript manifests
- **GPU-aware deployment** with automatic hardware detection
- **Network view** for discovering and accessing apps across nodes

### Why Package PMOVES for Pinokio?

| Benefit | Description |
|---------|-------------|
| **Simplified Deployment** | Users can install PMOVES agents with a single click |
| **Cross-Platform** | Scripts work on Windows, macOS, and Linux automatically |
| **GPU Orchestration** | Automatic detection and utilization of NVIDIA GPUs |
| **Network Discovery** | Apps automatically available across Pinokio network |
| **Agent Interpreter (P7)** | Pinokio 7+ can discover and interact with installed agents |

---

## Pinokio Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Pinokio Application                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Electron   │  │   Caddy     │  │   Pterm     │         │
│  │    UI       │  │  Proxy      │  │    CLI      │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                     API Layer                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ~/pinokio/api/                                       │  │
│  │    ├── app1.git/     (installed app)                 │  │
│  │    ├── app2.git/     (installed app)                 │  │
│  │    └── pmoves-agent/ (PMOVES agent package)          │  │
│  └──────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                   Script Runtime                             │
│  • shell.run  • fs.write   • request      • local.set      │
│  • git.clone  • fs.read    • dependencies • info.*        │
└─────────────────────────────────────────────────────────────┘
```

### Script Execution Flow

```
pinokio.js  ──►  Dynamic Menu Generation
     │
     ├── install.js  ──►  Clone repos, install dependencies
     ├── start.js    ──►  Launch the application
     ├── reset.js    ──►  Clean/reset state
     └── update.js   ──►  Pull latest changes
```

---

## PMOVES Agent Types & Pinokio Mapping

PMOVES uses a 7-tier agent taxonomy. Here's how each maps to Pinokio packaging patterns:

### Agent Class Prefixes

| Class | Prefix | Example | Pinokio Packaging |
|-------|--------|---------|-------------------|
| **Legendary** | `POWERFULMOVES` | Organization brand | N/A (doctrine level) |
| **Standard** | `PMOVES-` | Agent Zero, Archon | Full launcher with all scripts |
| **Specialized** | `Pmoves-` | Cipher Memory, Hyperdimensions | Full or simplified launcher |
| **Utility** | `pmoves-` | NATS, Qdrant, Neo4j | Often infrastructure-only |

### Service Tiers & Packaging

| Tier | Type | Element | Pinokio Pattern |
|------|------|---------|-----------------|
| 1 | Data | Earth | Database/infrastructure launcher |
| 2 | API | Water | API server launcher |
| 3 | LLM | Fire | Model download + inference server |
| 4 | Worker | Electric | Background service launcher |
| 5 | Media | Wind | Media processing pipeline |
| 6 | Agent | Psychic | Full agent runtime + UI |
| 7 | UI | Light | Frontend-only or static app |

### PMOVES Agents Ready for Pinokio Packaging

Based on [`pmoves/config/agent_registry.yaml`](../../config/agent_registry.yaml):

| Agent | Type | Port | Pinokio Package Name |
|-------|------|------|---------------------|
| Agent Zero | Agent+API | 8080 | `pmoves-agent-zero` |
| Archon | Agent+LLM | 8091 | `pmoves-archon` |
| Hi-RAG v2 | Worker+Data | 8086/8087 | `pmoves-hirag` |
| SupaSerch | Agent+LLM | 8099 | `pmoves-supaserch` |
| PMOVES.YT | Media+Worker | 8077 | `pmoves-yt` |
| Ultimate-TTS | Media+LLM | 7861 | `pmoves-ultimate-tts` |
| Jellyfin Bridge | Media+Data | 8093 | `pmoves-jellyfin-bridge` |
| Crush | UI+Agent | - | `pmoves-crush` |

---

## Folder Structure

### Standard Launcher Structure

For agents with backend services:

```
pmoves-agent-name/
├── pinokio/
│   ├── install.js        # Installation script
│   ├── start.js          # Launch script
│   ├── reset.js          # Reset/cleanup script
│   ├── update.js         # Update script (optional)
│   ├── pinokio.js        # Dynamic menu generator
│   └── logs/             # Runtime logs (auto-created)
├── pinokio.json          # Metadata (title, description, icon)
├── README.md             # Documentation
└── app/                  # Application code (or submodule)
```

### Serverless Web App Structure

For frontend-only applications:

```
pmoves-web-ui/
├── index.html            # Entry point (auto-launched)
├── pinokio.json          # Metadata only
└── README.md             # Documentation
```

### Script-Only Structure

For CLI tools and utilities:

```
pmoves-cli-tool/
├── pinokio/
│   ├── tool.js           # Main script
│   └── pinokio.js        # Menu linking to tool.js
├── pinokio.json          # Metadata
└── README.md             # Documentation
```

### PMOVES Multi-Service Structure

For multi-container deployments (like PMOVES core stack):

```
pmoves-services/
├── pinokio/
│   ├── install.js        # Clone submodules, setup env
│   ├── start-core.js     # Launch data + worker profiles
│   ├── start-agents.js   # Launch agent profile
│   ├── start-voice.js    # Launch voice stack
│   ├── start-gpu.js      # Launch GPU services
│   ├── stop.js           # Stop all profiles
│   ├── pinokio.js        # Dynamic menu with all options
│   └── logs/
├── pinokio.json
├── README.md
└── docker-compose.yml    # Reference to pmoves/docker-compose.yml
```

---

## Required Files

### 1. `pinokio.json` (Metadata)

```json
{
  "version": "1",
  "title": "PMOVES Agent Name",
  "description": "Brief description of what this agent does",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": "optional",
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-AgentName",
  "homepage": "https://pmoves.ai"
}
```

#### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `version` | ✅ | Schema version (always `"1"`) |
| `title` | ✅ | Display name in Pinokio UI |
| `description` | ✅ | Short description for app listing |
| `icon` | ✅ | Path to icon file (512x512 PNG recommended) |
| `platform` | ⚪ | Supported OS: `win32`, `darwin`, `linux` |
| `arch` | ⚪ | Architecture: `x64`, `arm64` |
| `gpu` | ⚪ | GPU requirement: `required`, `optional`, or omit |
| `author` | ⚪ | Author name |
| `repo` | ⚪ | Git repository URL |
| `homepage` | ⚪ | Project homepage URL |

### 2. `pinokio.js` (Dynamic Menu)

```javascript
// pinokio/pinokio.js
module.exports = {
  run: [
    {
      method: "script",
      params: {
        uri: "install.js",
        params: {}
      }
    },
    {
      method: "script.start",
      params: {
        uri: "start.js",
        params: { env: "production" }
      }
    }
  ],
  menu: [
    {
      id: "install",
      title: "Install",
      script: "install.js",
      default: !info.exists("app/node_modules")
    },
    {
      id: "start",
      title: "Start",
      script: "start.js",
      running: info.running("start.js"),
      default: info.exists("app/node_modules") && !info.running("start.js")
    },
    {
      id: "open",
      title: "Open WebUI",
      href: info.local("start.js", "url") || "http://localhost:8080",
      default: info.running("start.js")
    },
    {
      id: "reset",
      title: "Reset",
      script: "reset.js"
    }
  ]
}
```

### 3. `install.js` (Installation Script)

```javascript
// pinokio/install.js
module.exports = {
  run: [
    {
      method: "fs.rm",
      params: { path: "app" }
    },
    {
      method: "git.clone",
      params: {
        url: "https://github.com/POWERFULMOVES/PMOVES-AgentName",
        path: "app"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "npm install"
      }
    },
    {
      method: "notify",
      params: {
        message: "Installation complete!"
      }
    }
  ]
}
```

### 4. `start.js` (Launch Script)

```javascript
// pinokio/start.js
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "npm start",
        on: [{
          event: "/http://localhost:[0-9]+/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1]  // Captured URL from regex
      }
    }
  ]
}
```

### 5. `reset.js` (Cleanup Script)

```javascript
// pinokio/reset.js
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "rm -rf node_modules"
      }
    },
    {
      method: "fs.rm",
      params: { path: "app/.env" }
    }
  ]
}
```

---

## Script APIs

### Core APIs

#### `shell.run` - Execute Shell Commands

```javascript
{
  method: "shell.run",
  params: {
    path: "app",                    // Working directory
    message: "npm start",           // Command to run
    env: {                          // Environment variables (optional)
      NODE_ENV: "production",
      PORT: "8080"
    },
    on: [                           // Completion conditions
      {
        event: "/Server listening/",
        done: true
      }
    ]
  }
}
```

#### `git.clone` - Clone Repository

```javascript
{
  method: "git.clone",
  params: {
    url: "https://github.com/user/repo",
    path: "app",
    branch: "main"  // Optional
  }
}
```

#### `fs.write` / `fs.read` - File Operations

```javascript
// Write file
{
  method: "fs.write",
  params: {
    path: "app/.env",
    text: "API_KEY=xxx\nPORT=8080"
  }
}

// Read file
{
  method: "fs.read",
  params: {
    path: "app/.env"
  },
  returns: "env_content"  // Stored in input.env_content
}
```

#### `request` - HTTP Requests

```javascript
{
  method: "request",
  params: {
    uri: "https://api.example.com/data",
    method: "GET",
    headers: {
      "Authorization": "Bearer xxx"
    }
  }
}
```

#### `local.set` / `local.get` - Local Variables

```javascript
// Set local variable (persists during script run)
{
  method: "local.set",
  params: {
    url: "http://localhost:8080",
    status: "running"
  }
}

// Access in pinokio.js: info.local("start.js", "url")
```

### Conditional Execution

```javascript
{
  method: "shell.run",
  params: {
    path: "app",
    // Platform-specific commands
    message: platform === "win32" 
      ? "npm run start:windows"
      : platform === "darwin"
        ? "npm run start:macos"
        : "npm run start:linux"
  }
}
```

### GPU Detection

```javascript
{
  method: "shell.run",
  params: {
    path: "app",
    message: gpu === "nvidia"
      ? "python start.py --gpu"
      : "python start.py --cpu"
  }
}
```

---

## Packaging Patterns by Agent Type

### Pattern 1: API/Worker Services (Tier 2-4)

**Examples:** Hi-RAG v2, Extract Worker, Channel Monitor

```javascript
// pinokio/start.js for API/Worker
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "uvicorn main:app --host 0.0.0.0 --port 8086",
        on: [{
          event: "/Uvicorn running on/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1]
      }
    }
  ]
}
```

### Pattern 2: LLM Services (Tier 3)

**Examples:** TensorZero, DeepResearch, Llama Lab

```javascript
// pinokio/install.js for LLM with model download
module.exports = {
  run: [
    {
      method: "git.clone",
      params: {
        url: "https://github.com/POWERFULMOVES/PMOVES-LLM-Service",
        path: "app"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "pip install -r requirements.txt"
      }
    },
    {
      method: "notify",
      params: {
        message: "Downloading model weights (this may take a while)..."
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "python download_model.py"
      }
    }
  ]
}
```

### Pattern 3: Media Services (Tier 5)

**Examples:** PMOVES.YT, Ultimate-TTS, FFmpeg-Whisper

```javascript
// pinokio/start.js for GPU-accelerated media
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: gpu === "nvidia"
          ? "python launch.py --gpu --port 7861"
          : "python launch.py --cpu --port 7861",
        env: {
          GRADIO_SERVER_NAME: "0.0.0.0",
          CUDA_VISIBLE_DEVICES: "0"
        },
        on: [{
          event: "/Running on (http:\\/\\/[0-9.:]+)/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1]
      }
    }
  ]
}
```

### Pattern 4: Full Agent Runtime (Tier 6)

**Examples:** Agent Zero, Archon, SupaSerch

```javascript
// pinokio/install.js for full agent with MCP servers
module.exports = {
  run: [
    {
      method: "git.clone",
      params: {
        url: "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero",
        path: "app"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "pip install -r requirements.txt"
      }
    },
    {
      method: "fs.write",
      params: {
        path: "app/.env",
        text: `
SUPABASE_URL=${args.supabase_url}
SUPABASE_KEY=${args.supabase_key}
NATS_URL=nats://localhost:4222
        `.trim()
      }
    },
    {
      method: "notify",
      params: {
        message: "Agent Zero installed. Configure MCP servers in .env"
      }
    }
  ]
}
```

### Pattern 5: UI-Only Apps (Tier 7)

**Examples:** Crush, MAI-UI, Hyperdimensions

```javascript
// pinokio/start.js for Next.js/React UI
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "npm run dev",
        env: {
          NEXT_PUBLIC_API_URL: args.api_url || "http://localhost:8080"
        },
        on: [{
          event: "/Local:\\s+(http:\\/\\/[0-9.:]+)/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        url: input.event[1]
      }
    }
  ]
}
```

### Pattern 6: Docker Compose Stack

**Examples:** PMOVES Core Services, Monitoring Stack

```javascript
// pinokio/start-core.js for Docker Compose
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "..",  // Parent directory with docker-compose.yml
        message: "docker compose --profile data --profile workers up -d",
        on: [{
          event: "/Container .* Started/",
          done: true
        }]
      }
    },
    {
      method: "local.set",
      params: {
        status: "running",
        services: ["nats", "qdrant", "neo4j", "meilisearch"]
      }
    }
  ]
}
```

---

## Examples

### Complete Example: PMOVES Agent Zero

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

**pinokio.json:**
```json
{
  "version": "1",
  "title": "PMOVES Agent Zero",
  "description": "Primary L1 orchestrator with embedded agent runtime and MCP API",
  "icon": "icon.png",
  "platform": ["win32", "darwin", "linux"],
  "arch": ["x64", "arm64"],
  "gpu": "optional",
  "author": "POWERFULMOVES",
  "repo": "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero"
}
```

**pinokio/pinokio.js:**
```javascript
module.exports = {
  run: [
    {
      method: "script",
      params: { uri: "install.js" }
    }
  ],
  menu: [
    {
      id: "install",
      title: "Install",
      script: "install.js",
      default: !info.exists("app/.installed")
    },
    {
      id: "start",
      title: "Start Agent",
      script: "start.js",
      running: info.running("start.js"),
      default: info.exists("app/.installed") && !info.running("start.js")
    },
    {
      id: "api",
      title: "Open API (Swagger)",
      href: info.local("start.js", "url") 
        ? `${info.local("start.js", "url")}/docs` 
        : "http://localhost:8080/docs",
      default: info.running("start.js")
    },
    {
      id: "mcp",
      title: "MCP Endpoint",
      href: info.local("start.js", "url") 
        ? `${info.local("start.js", "url")}/mcp` 
        : "http://localhost:8080/mcp"
    },
    {
      id: "update",
      title: "Update",
      script: "update.js"
    },
    {
      id: "reset",
      title: "Reset",
      script: "reset.js"
    }
  ]
}
```

**pinokio/install.js:**
```javascript
module.exports = {
  run: [
    {
      method: "fs.rm",
      params: { path: "app" }
    },
    {
      method: "git.clone",
      params: {
        url: "https://github.com/POWERFULMOVES/PMOVES-Agent-Zero",
        path: "app",
        branch: "main"
      }
    },
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "pip install -r requirements.txt"
      }
    },
    {
      method: "fs.write",
      params: {
        path: "app/.env.example",
        text: `
# PMOVES Agent Zero Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_key
NATS_URL=nats://localhost:4222
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# MCP Servers (optional)
A0_MCP_SERVERS=
  archon: "mcp://http?endpoint=http://localhost:8091";
  neo4j: "mcp://neo4j?url=bolt://localhost:7687";
        `.trim()
      }
    },
    {
      method: "fs.write",
      params: {
        path: "app/.installed",
        text: new Date().toISOString()
      }
    },
    {
      method: "notify",
      params: {
        message: "Agent Zero installed! Copy .env.example to .env and configure."
      }
    }
  ]
}
```

**pinokio/start.js:**
```javascript
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "python main.py",
        env: {
          HOST: "0.0.0.0",
          PORT: "8080"
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
        url: input.event[1]
      }
    }
  ]
}
```

### Complete Example: PMOVES Services (Multi-Profile)

**pinokio/pinokio.js:**
```javascript
module.exports = {
  menu: [
    {
      id: "install",
      title: "Install Dependencies",
      script: "install.js",
      default: !info.exists(".installed")
    },
    // Divider
    { type: "divider", title: "Service Profiles" },
    // Core data layer
    {
      id: "start-data",
      title: "Start Data Layer",
      description: "NATS, Qdrant, Neo4j, Meilisearch",
      script: "start-data.js",
      running: info.running("start-data.js")
    },
    // Workers
    {
      id: "start-workers",
      title: "Start Workers",
      description: "Hi-RAG, Extract, PDF Ingest",
      script: "start-workers.js",
      running: info.running("start-workers.js")
    },
    // Agents
    {
      id: "start-agents",
      title: "Start Agents",
      description: "Agent Zero, Archon",
      script: "start-agents.js",
      running: info.running("start-agents.js")
    },
    // GPU services
    {
      id: "start-gpu",
      title: "Start GPU Services",
      description: "TTS, Media Analysis",
      script: "start-gpu.js",
      running: info.running("start-gpu.js"),
      disabled: gpu !== "nvidia"
    },
    // Divider
    { type: "divider", title: "Utilities" },
    // Stop all
    {
      id: "stop-all",
      title: "Stop All Services",
      script: "stop-all.js"
    },
    // Status
    {
      id: "status",
      title: "Service Status",
      script: "status.js"
    }
  ]
}
```

---

## Testing & Validation

### Local Testing with Pterm

```bash
# Test install script
pterm start /path/to/pmoves-agent/install.js

# Test start script
pterm start /path/to/pmoves-agent/start.js

# View logs
pterm logs /path/to/pmoves-agent
```

### Validation Checklist

Before publishing a PMOVES Pinokio package:

- [ ] **Metadata Complete**
  - [ ] `pinokio.json` has all required fields
  - [ ] Icon is 512x512 PNG
  - [ ] Description is clear and concise

- [ ] **Scripts Work**
  - [ ] `install.js` completes without errors
  - [ ] `start.js` launches the service
  - [ ] URL capture works with `on` event
  - [ ] `reset.js` cleans up properly

- [ ] **Cross-Platform**
  - [ ] Tested on Windows, macOS, Linux (or documented limitations)
  - [ ] Platform-specific paths handled correctly
  - [ ] Environment variables work across platforms

- [ ] **GPU Handling**
  - [ ] GPU detection works
  - [ ] Fallback to CPU when no GPU
  - [ ] `gpu` field set correctly in `pinokio.json`

- [ ] **Documentation**
  - [ ] README.md explains what the agent does
  - [ ] Configuration options documented
  - [ ] Environment variables listed
  - [ ] Ports and endpoints documented

- [ ] **Dynamic Menu**
  - [ ] Default states change based on installation status
  - [ ] Running state reflected in menu
  - [ ] URLs appear when service is running

### Automated Testing

Create a test script:

```javascript
// pinokio/test.js
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "app",
        message: "npm test"
      }
    },
    {
      method: "request",
      params: {
        uri: "http://localhost:8080/healthz",
        method: "GET"
      }
    },
    {
      method: "notify",
      params: {
        message: input.status === 200 
          ? "✅ All tests passed"
          : "❌ Health check failed"
      }
    }
  ]
}
```

---

## Distribution

### Publishing to Pinokio Registry

1. **Host on GitHub**
   ```bash
   git push origin main
   ```

2. **Create Release Tag**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Submit to Pinokio**
   - Visit https://pinokio.computer
   - Submit app URL: `https://github.com/POWERFULMOVES/PMOVES-AgentName`

### PMOVES Internal Distribution

For PMOVES team members, packages are available at:

```
pbnj/pinokio/api/
├── pmoves-agent-zero/     # Agent Zero launcher
├── pmoves-archon/         # Archon launcher
├── pmoves-services/       # Multi-service launcher
├── pmoves-ultimate-tts/   # TTS Studio launcher
└── pmoves-pbnj/           # PBnJ control panel
```

**Installation via Symlink:**

```bash
# macOS/Linux
ln -s /path/to/PMOVES.AI/pbnj/pinokio/api/pmoves-agent-zero \
  ~/pinokio/api/pmoves-agent-zero

# Windows (PowerShell)
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\pinokio\api\pmoves-agent-zero" `
  -Target "C:\path\to\PMOVES.AI\pbnj\pinokio\api\pmoves-agent-zero"
```

### Version Management

```json
// pinokio.json with versioning
{
  "version": "1",
  "title": "PMOVES Agent Zero",
  "engine": "0.1.0",  // Minimum Pinokio version
  "pmoves_version": "1.4.0",  // PMOVES taxonomy version
  ...
}
```

---

## Troubleshooting

### Common Issues

#### 1. Script Fails Silently

**Check logs:**
```bash
# Pinokio logs location
~/pinokio/api/pmoves-agent/logs/

# View with Pterm
pterm logs pmoves-agent
```

#### 2. Port Already in Use

**Add port detection:**
```javascript
{
  method: "shell.run",
  params: {
    message: platform === "win32"
      ? "netstat -ano | findstr :8080"
      : "lsof -i :8080",
    throws: false  // Don't fail if port is free
  }
}
```

#### 3. Environment Variables Not Loading

**Debug env:**
```javascript
{
  method: "shell.run",
  params: {
    message: platform === "win32"
      ? "set"  // Windows
      : "env", // Unix
    path: "app"
  }
}
```

#### 4. GPU Not Detected

**Manual GPU check:**
```javascript
{
  method: "shell.run",
  params: {
    message: "nvidia-smi",
    throws: false
  }
}
```

#### 5. Regex Pattern Not Matching

**Debug event capture:**
```javascript
{
  method: "shell.run",
  params: {
    message: "npm start",
    on: [
      {
        event: "/.*/",  // Match everything
        done: false
      },
      {
        event: "/http:\\/\\/[0-9.:]+/",
        done: true
      }
    ]
  }
}
```

### Debug Mode

Enable verbose logging:

```javascript
// pinokio/start.js with debug
module.exports = {
  debug: true,  // Enable debug mode
  run: [
    // ... scripts
  ]
}
```

### Getting Help

1. **Pinokio Docs:** https://pinokio.co/docs
2. **PMOVES Discord:** [Join PMOVES Community](https://discord.gg/pmoves)
3. **GitHub Issues:** https://github.com/POWERFULMOVES/PMOVES.AI/issues

---

## Appendix A: PMOVES Agent Registry Quick Reference

| Agent | Class | Tier | Port | GPU | Pinokio Package |
|-------|-------|------|------|-----|-----------------|
| Agent Zero | Standard | 6+2 | 8080 | Optional | `pmoves-agent-zero` |
| Archon | Standard | 6+3 | 8091 | Optional | `pmoves-archon` |
| Hi-RAG v2 | Standard | 4+1 | 8086/8087 | Optional | `pmoves-hirag` |
| SupaSerch | Standard | 6+3 | 8099 | Optional | `pmoves-supaserch` |
| DeepResearch | Standard | 3+4 | 8098 | Optional | `pmoves-deepresearch` |
| TensorZero | Standard | 2+3 | 3030 | No | `pmoves-tensorzero` |
| Flute Gateway | Standard | 2+5 | 8055 | Optional | `pmoves-flute` |
| PMOVES.YT | Standard | 5+4 | 8077 | Optional | `pmoves-yt` |
| Ultimate-TTS | Standard | 5+3 | 7861 | Recommended | `pmoves-ultimate-tts` |
| FFmpeg-Whisper | Standard | 5+4 | 8078 | Recommended | `pmoves-whisper` |
| Media-Video | Standard | 5+4 | 8079 | Required | `pmoves-media-video` |
| Jellyfin Bridge | Specialized | 5+1 | 8093 | No | `pmoves-jellyfin-bridge` |
| Cipher Memory | Specialized | 1+6 | 8096 | No | `pmoves-cipher` |
| Crush | Standard | 7+6 | - | No | `pmoves-crush` |
| EvoSwarm | Standard | 4+6 | 8113 | Required | `pmoves-evoswarm` |

---

## Appendix B: Environment Variables Reference

### Common PMOVES Environment Variables

```bash
# Supabase (required for most agents)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# NATS (event bus)
NATS_URL=nats://localhost:4222

# LLM Providers (at least one required)
OPENAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
GOOGLE_API_KEY=xxx

# Vector DBs
QDRANT_URL=http://localhost:6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxx

# Search
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_KEY=xxx

# Storage (Supabase Storage S3)
MINIO_ENDPOINT=http://localhost:65421/storage/v1/s3
MINIO_ACCESS_KEY=xxx
MINIO_SECRET_KEY=xxx

# GPU
CUDA_VISIBLE_DEVICES=0
```

---

## Appendix C: Pinokio Pterm CLI Reference

```bash
# Start an app
pterm start /path/to/app

# Stop an app
pterm stop /path/to/app

# View logs
pterm logs /path/to/app

# Send notification
pterm push "Message"

# Clipboard access
pterm clipboard read
pterm clipboard write "text"

# File picker
pterm filepicker
pterm filepicker --directory

# Version
pterm --version
```

---

**Document maintained by:** PMOVES Documentation Team  
**Related Documentation:**
- [PMOVES Agent Registry](../../config/agent_registry.yaml)
- [PBnJ README](../../../pbnj/README.md)
- [Pinokio Documentation](https://pinokio.co/docs)
- [CLAUDE.md (Pinokio Rules)](../../../CLAUDE.md)
