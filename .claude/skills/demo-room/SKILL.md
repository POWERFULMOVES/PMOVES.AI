---
name: demo-room
description: >
  Launch the PMOVES Demo Room: starts Agent Zero locally, loads 4090 Claude Code claws (skills),
  and surfaces HERMES V4 as the reasoning assist. Publishes p7.nats.launch to trigger the P7
  room-aware stage manager. Use /demo-room to enter demo mode from any node.
disable-model-invocation: true
---

# demo-room

Launch the PMOVES demo room from 4090 Claude Code.

## What it spawns

| Suit | Provider | Role |
|------|----------|------|
| Agent Zero | `http://localhost:8080` | Orchestration backbone |
| 4090 Claude Code | Current session | Code claws + skills auto-loaded |
| HERMES V4 (`hermes3:8b`) | Ollama local | Reasoning assist |

## Prerequisites

1. **Ollama running locally** with `hermes3:8b` pulled:
   ```bash
   ollama pull hermes3:8b
   ```
2. **PMOVES-Agent-Zero** submodule initialized:
   ```bash
   git submodule update --init PMOVES-Agent-Zero
   ```
3. **Agent Zero venv** created:
   ```bash
   cd PMOVES-Agent-Zero && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
   ```

## Pinokio launch (one-click)

Open PBnJ in Pinokio → **Launch Demo Room** button.

Equivalent shell:
```bash
pterm start PMOVES-pinokio/api/pmoves-pbnj/demo.js
```

## Manual launch

```bash
cd PMOVES-Agent-Zero
.venv/Scripts/python.exe run_ui.py --port 8080
# then open http://localhost:8080
```

## NATS event published on launch

```json
{
  "room": "demo.room.rehearsal",
  "stage": "rehearsal",
  "suits": ["agent-zero-local", "4090-claws", "hermes-v4"]
}
```
Subject: `p7.nats.launch`

## Room manifest

`pmoves/config/rooms/demo.room.json` — defines panels, apps, skill bindings, P7 subjects.

## Stop

In Pinokio UI: click the stop button on the demo.js terminal.
Or: `pterm stop PMOVES-pinokio/api/pmoves-pbnj/demo.js`
