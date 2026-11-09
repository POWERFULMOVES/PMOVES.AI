# Crush in Pinokio — Wiring + Bootstrap Plan

> **GRAPHITI_MARK:** CRUSH-GLM52::CRUSH-IN-PINOKIO-PLAN::2026-08-04
> **From:** ◇ Crush (Z890, GLM-5.2)
> **Date:** 2026-08-04

## Vision

Crush becomes a first-class launcher in the PMOVES Pinokio fork — sitting alongside
Claude Code, Codex, Hermes, and OpenCode. Launching Crush from Pinokio bootstraps
the full PMOVES stack (env, CHIT, TensorZero, MCP servers, LSP) before dropping
into the companion terminal. One-click from the Pinokio desktop → fully wired agent.

## Current State

### What exists (barebones plugin — NOT PMOVES-aware)
`D:/pinokio/plugin/code/crush/pinokio.js` — 15 lines, blindly runs
`npx -y @charmland/crush@latest` with zero PMOVES bootstrap.

### What exists (PMOVES bootstrap — mature, NOT Pinokio-integrated)
| Component | Path | What it does |
|-----------|------|-------------|
| `crush-pmoves` | `pmoves/scripts/crush-pmoves` | One-shot: env → bootstrap → `exec crush` |
| `crush-fleet-bootstrap.sh` | `pmoves/scripts/crush-fleet-bootstrap.sh` | CHIT passphrase + config gen + LSP install |
| `crush_configurator.py` | `pmoves/tools/crush_configurator.py` | Generates crush.json (TensorZero→Z.AI→Ollama) |
| `mcp_config_generator.py` | `pmoves/tools/mcp_config_generator.py` | `render_crush()` — MCP server block |
| `crush-env.sh` | `pmoves/scripts/crush-env.sh` | Resolves tier env + Tailscale IPs |

### The Gap
Nothing connects Pinokio's launcher to the PMOVES bootstrap. The existing plugin
runs raw Crush with no provider config, no MCP servers, no CHIT signing, no
context paths, no LSP servers.

### Reference Patterns

| Pattern | Source | What it shows |
|---------|--------|---------------|
| **Plugin launcher** | `D:/pinokio/plugin/code/claude/pinokio.js` | Cross-platform Win32 bash shim + `{{args.cwd}}` |
| **App launcher** | `D:/pinokio/api/hermes-agent.pinokio.git/` | Full lifecycle: install → setup → launch → gateway → update → reset |
| **PMOVES wrapper** | `pmoves/scripts/crush-pmoves` | Already probes `$HOME/pinokio/api/PMOVES.AI` |

## Architecture Decision: Enhance the Plugin

We enhance the **existing plugin launcher** (`D:/pinokio/plugin/code/crush/pinokio.js`)
rather than creating a new app launcher. Reasons:

1. The plugin pattern is what claude/codex use — Crush is the same class of tool
2. The PMOVES bootstrap (`crush-pmoves`) is already a shell script that Pinokio can invoke
3. The hermes app-launcher pattern (install.js + venv + gateway lifecycle) is for
   server-backed agents; Crush is a terminal agent, not a server
4. Keeping it as a plugin means it shows up in the Pinokio "Code" section where
   users already find claude/codex

## Implementation Plan (5 files)

### 1. Enhanced Plugin Launcher — `pinokio.js`

Replace the bare `npx` call with a PMOVES-bootstrap-aware launcher that:
- Resolves the PMOVES.AI repo root (same probe as `crush-pmoves`)
- Calls `make -C pmoves crush-bootstrap` to generate crush.json + install LSPs
- Then launches `crush` interactively with the full env

Cross-platform: Win32 uses Pinokio's bundled bash (like claude/codex launchers).

```javascript
module.exports = {
  title: "Crush (PMOVES)",
  icon: "crush.png",
  link: "https://github.com/charmbracelet/crush",
  run: [{
    when: "{{platform === 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      shell: "{{kernel.path('bin/miniconda/Library/bin/bash.exe')}}",
      conda: { skip: true },
      env: {
        CLAUDE_CODE_GIT_BASH_PATH: "{{kernel.path('bin/miniconda/Library/bin/bash.exe')}}"
      },
      message: "cd {{args.cwd}} && make -C pmoves crush-bootstrap 2>/dev/null; crush",
      path: "{{args.cwd}}",
      input: true,
      buffer: 1024
    }
  }, {
    when: "{{platform !== 'win32'}}",
    id: "run",
    method: "shell.run",
    params: {
      message: "cd {{args.cwd}} && make -C pmoves crush-bootstrap 2>/dev/null; crush",
      path: "{{args.cwd}}",
      input: true,
      buffer: 1024
    }
  }]
}
```

### 2. Registry Entry — `pmoves/configs/pinokio-apps/curated/crush.yaml`

Following `pinokio-app.v1.schema.json`:

```yaml
slug: crush
display_name: "Crush (PMOVES)"
category: agent
description: >
  Charm Crush CLI with full PMOVES bootstrap — TensorZero provider,
  MCP servers, CHIT trail signing, context paths, LSP diagnostics.
  The companion at the terminal where Human, AI, and System converge.
owner: pmoves
launcher_script: plugin/code/crush/pinokio.js
launcher_type: plugin
gpu_required: false
gpu_reservation_mb: 0
autostart: false
network_exposure:
  layer_1:
    reachable: true
    description: "venv — no external deps beyond npx"
  layer_2:
    reachable: false
  layer_3:
    reachable: true
    description: "reaches TensorZero :3030, NATS :4222, Cipher :8105 via Docker network"
  layer_4:
    reachable: false
    description: "not publicly exposed (terminal agent)"
tags: [agent, terminal, companion, pmoves-native]
```

### 3. Install Script — `install.js` (optional, for first-time setup)

Separate from the launcher — handles LSP installation and Python deps:

```javascript
module.exports = {
  run: [{
    method: "shell.run",
    params: {
      message: "npm install -g pyright typescript-language-server",
      path: "{{args.cwd}}"
    }
  }, {
    method: "shell.run",
    params: {
      message: "pip install ruff pyyaml typer[all]",
      path: "{{args.cwd}}"
    }
  }]
}
```

### 4. Pinokio Bridge Skill Enhancement

The existing `pinokio-bridge-skill` already wraps Pinokio 8's app management.
Add a Crush-specific entry that:
- Lists Crush as a launchable agent (alongside ComfyUI, TTS engines)
- Exposes `/pinokio/crush/launch` → triggers the plugin launcher
- Reports Crush running state via `pterm status`

### 5. Makefile Target — `crush-pinokio-launch`

A convenience target that validates Pinokio is running and launches Crush via pterm:

```makefile
crush-pinokio-launch: ## Launch Crush via Pinokio pterm (requires Pinokio running)
	@pterm start plugin/code/crush/pinokio.js --cwd $(CURDIR)/..
```

## Bootstrap Sequence (what happens when user clicks "Crush (PMOVES)" in Pinokio)

```
1. Pinokio launches pinokio.js → shell.run with {{args.cwd}} = PMOVES.AI repo root
2. Bash enters the repo, runs `make -C pmoves crush-bootstrap`
   ├── Resolves CHIT passphrase from env.tier-data
   ├── Installs CLI wrappers (crush-pmoves, pmoves-mini) to ~/.local/bin
   ├── Runs crush_configurator.py → generates ~/.config/crush/crush.json
   │   ├── Provider: Z.AI GLM-5.2 (large) + GLM-5-Turbo (small)
   │   ├── MCP: cipher, agent-zero, supabase, docker-gateway, huggingface
   │   ├── Context paths: CRUSH.md, AGENT_TRAIL.md, ROADMAP, SMOKETESTS
   │   └── LSP: gopls, pyright, typescript-language-server
   ├── Tests CHIT trail signing (HMAC-SHA256)
   └── Reports status
3. Bash drops into `crush` interactive terminal
   ├── Crush loads crush.json (provider + MCP + context)
   ├── Discovers AGENT_TRAIL.md → finds identity ◇
   ├── Connects to MCP servers (cipher, agent-zero, etc.)
   └── User is in the companion terminal — ready to code
```

## What Makes This Different from Bare `npx crush`

| Feature | Bare Plugin (current) | PMOVES Plugin (proposed) |
|---------|----------------------|--------------------------|
| Provider | Default (asks user) | Z.AI GLM-5.2 via coding plan |
| MCP servers | None | 8 PMOVES MCP servers |
| CHIT signing | None | HMAC-SHA256 trail signing |
| Context paths | None | 8 PMOVES context paths |
| LSP diagnostics | None | pyright + typescript + ruff |
| Model fallback | None | TensorZero → Z.AI → Ollama |
| Fleet awareness | None | AGENT_TRAIL + agent_signatures |

## Lanes to Resume or Claim

### Claim (unclaimed, Crush lane)
1. **Crush-in-Pinokio wiring** (this plan — unclaimed)
2. **Model side: Unsloth fine-tuning + HF MCP** (CRUSH-GLM52 assigned lane per AGNOTE)
3. **PMOVES.YT catalog → HF collection** (model side, post-cookie bootstrap)

### Resume (our work, needs follow-up)
4. **Jetson combiner on-device bootstrap** — artifacts on main, need SSH to JONS nodes
5. **Submodule fleet reconciliation** — 38+ dirty submodules still
6. **G3 fitness collector** — tool on main, needs TensorZero /metrics to populate

### Coordinate (other agents' work, don't touch)
7. **Traefik** — Z890-Claude active now
8. **Pinokio P8 fork sync** — Mavis queued lane #1 (no-op per audit)
9. **pinokio_bridge default-up** — Mavis queued lane #2 (SHIPPED per #2293)
10. **Voice S6-S10** — blocked on operator §10 Q3/Q6/Q10

## Execution Order

1. **Write the enhanced `pinokio.js`** (10 min) — replace bare npx with bootstrap+launch
2. **Write the registry YAML** (5 min) — `pmoves/configs/pinokio-apps/curated/crush.yaml`
3. **Test locally** — `pterm start plugin/code/crush/pinokio.js --cwd D:/PMOVES.AI/PMOVES.AI`
4. **Commit + PR** — the plugin launcher lives in Pinokio's install (D:/pinokio/), the
   registry entry lives in PMOVES.AI
5. **Document** — update CRUSH.md + CRUSH_OPERATOR_HOME.md with the Pinokio launch path
6. **Sign trail** — `make sign-trail AGENT=crush-z890 SUMMARY="Crush in Pinokio wiring"`
