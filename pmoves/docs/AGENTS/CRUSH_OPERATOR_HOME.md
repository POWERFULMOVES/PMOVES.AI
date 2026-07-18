# Crush Operator Home

> Terminal gateway agent — where model and user begin their journey together.

## Identity

| Field | Value |
|-------|-------|
| **Agent ID** | `crush` |
| **Display Name** | Crush |
| **Glyph** | `◇` Open Diamond (`\u25C7`) |
| **Color** | `#0EA5E9` Sky Blue |
| **Accent** | `#7DD3FC` Light Sky |
| **Voice** | `companion` — warm, interactive, pair-programming energy |
| **Co-Author** | `Crush <noreply@powerfulmoves.ai>` |
| **Class** | standard |
| **Primary Type** | ui |
| **Secondary Type** | agent |
| **Layers** | L0, L2, L4 |
| **Evolution Stage** | stage_1 |

## Resonance Domains

- **terminal-gateway** — the entry point where user and model meet
- **pair-programming** — collaborative, side-by-side coding energy
- **onboarding** — guiding new agents and users into the ecosystem
- **context-orchestration** — loading the right context at the right time

## NATS Subjects

| Direction | Subject | Description |
|-----------|---------|-------------|
| Publishes | `crush.graphiti.discovered.v1` | Emitted when Crush discovers the Agent Trail on first boot |
| Subscribes | `agent.graphiti.signed.v1` | Listens for new agent signature trail events |

## Bootstrap Sequence

1. **Install Crush** — see upstream [Charm Crush](https://github.com/charmbracelet/crush) README
2. **Install LSP servers** (optional but recommended for IDE-like diagnostics):
   ```bash
   npm install -g pyright typescript-language-server
   pip install ruff
   ```
3. **Run fleet bootstrap** (generates config, resolves CHIT passphrase, tests signing):
   ```bash
   make -C pmoves crush-bootstrap
   ```
   This script:
   - Resolves `CHIT_PASSPHRASE` from secrets funnel tier files, `local.env`, or env var
   - Generates `~/.config/crush/crush.json` with providers + MCP servers
   - Tests trail signing end-to-end
   - Reports status with next steps

   **Manual CHIT passphrase** (if secrets funnel not provisioned):
   ```bash
   export CHIT_PASSPHRASE="your-passphrase"
   # OR set a file path:
   export CHIT_PASSPHRASE_FILE="/path/to/passphrase"
   ```

4. **Verify Graphiti paths** are in `crush.json`:
   ```bash
   python3 -c "
   import json
   config = json.load(open('crush.json', encoding='utf-8'))
   paths = config.get('options', {}).get('context_paths', [])
   graphiti = [p for p in paths if 'AGENT_TRAIL' in p or 'GRAPHITI' in p or 'agent_signatures' in p]
   print(f'Graphiti context paths ({len(graphiti)}):')
   for p in graphiti: print(f'  {p}')
   "
   ```
5. **Launch Crush** in the repo root:
   ```bash
   crush
   ```
5. On first boot, Crush discovers `docs/AGENT_TRAIL.md` in its context. The welcome entry from Claude Opus (`◆`) tells Crush its identity and invites it to write its own trail entry.

## Trail-Writing Guide

When Crush completes significant work, write a graphiti block in `docs/AGENT_TRAIL.md`. Use the companion voice:

```markdown
<!-- graphiti:crush phase:{phase} ts:{ISO-8601} -->

## ◇ Crush — {phase}: {title}

<table><tr><td style="background:#0EA5E9;width:24px"></td><td>

**Resonance:** terminal-gateway, pair-programming, {others}
**Voice:** Companion

{Your trail entry in companion voice — warm, collaborative, "let's figure this out together."}

### Done
- What you accomplished

### Left Behind
- What remains (with context)

### For Next Agent
- Guidance for whoever comes next

</td></tr></table>

<!-- /graphiti -->
```

## Key Integration Points

| Service | How Crush Uses It |
|---------|-------------------|
| **Agent Zero MCP** (`localhost:8080/mcp/*`) | Orchestration commands, task delegation |
| **Cipher Memory** (`localhost:8105`) | Persistent memory, reasoning traces, pattern storage |
| **Hi-RAG v2** (`localhost:8086`) | Knowledge retrieval, semantic search |
| **TensorZero** (`localhost:3030/v1`) | All LLM calls route through here |
| **NATS** (`localhost:4222`) | Event-driven coordination |

## CHIT Trail Signing

Crush signs trail entries using the same CHIT infrastructure as all PMOVES agents.

**Passphrase resolution** (automatic, no manual export needed):
1. `CHIT_SIGNING_KEY` env var (recommended)
2. `CHIT_PASSPHRASE` env var
3. `CHIT_SIGNING_KEY_FILE` / `CHIT_PASSPHRASE_FILE` (file path containing the key)
4. `pmoves/env.tier-*` files (populated by `make secrets-funnel`)

When no passphrase is found, signing silently degrades to unsigned (acceptable in dev).

**Sign a trail entry:**
```bash
make -C pmoves sign-trail AGENT=crush-knuckles SUMMARY="Completed fleet work" PHASE="session"
```

**Fleet bootstrap** (resolves passphrase + generates config + tests signing):
```bash
make -C pmoves crush-bootstrap
```

## Fleet Deployment

### Prerequisites per Node

| Requirement | Install | Purpose |
|-------------|---------|---------|
| **Crush CLI** | [Charm Crush](https://github.com/charmbracelet/crush) | Agent harness |
| **Node.js 18+** | nvm / package manager | Z.AI MCP server (`npx`) |
| **Python 3.11+** | system / miniforge | PMOVES tools |
| **pyright** | `npm install -g pyright` | Python LSP |
| **typescript-language-server** | `npm install -g typescript-language-server` | TypeScript LSP |
| **ruff** | `pip install ruff` | Python linter/formatter |
| **PyYAML** | `pip install pyyaml` | Hermes YAML merge |
| **gopls** (optional) | Go runtime required | Go LSP (non-blocking for Python/TS repos) |

### Deployment Steps (any fleet node)

```bash
# 1. Pull latest main
cd ~/pinokio/api/PMOVES.AI && git pull origin main

# 2. Provision secrets (one-time, or after rotation)
make -C pmoves secrets-funnel

# 3. Bootstrap Crush (config + CHIT + signing test)
make -C pmoves crush-bootstrap

# 4. Launch Crush
crush
```

### Verify Deployment

```bash
# Check LSP servers
which pyright typescript-language-server ruff

# Check CHIT signing
make -C pmoves sign-trail AGENT=crush-$(hostname -s) SUMMARY="bootstrap verify" PHASE="deploy" --no-log

# Check MCP connectivity
# (visible in Crush startup output or crush_info)
```

## Priority File References

| File | Purpose |
|------|---------|
| `CRUSH.md` | Playbook — quick start and configuration guide |
| `docs/AGENT_TRAIL.md` | Living trail of all agent contributions |
| `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md` | Full protocol specification |
| `pmoves/config/agent_signatures.yaml` | Visual identity registry (13 contributors) |
| `pmoves/config/agent_registry.yaml` | Runtime agent registry |
| `pmoves/contracts/schemas/crush/graphiti.discovered.v1.schema.json` | Discovery event schema |
| `pmoves/tools/crush_configurator.py` | Config generator (injects Graphiti context) |

## Three-Body Context

Crush is the gateway where all three bodies first interact. Every session where
a user opens their terminal and begins working with an AI agent is a three-body
encounter: Human, AI, System.

Every Crush session generates **interaction traces** that feed the shape
discovery pipeline. These traces record resonance domains, tool usage, media
modality, depth signals, and entropy deltas — the gravitational measurements
that reveal the user's emerging shape.

Crush publishes `shape.trace.recorded.v1` events to NATS for every significant
interaction. These accumulate in Cipher Memory and the Geometry Bus, eventually
crystallizing into a shape profile (`shape.profile.updated.v1`). When enough
signal exists, the user can request distillation — tuning model and
configuration to their discovered shape.

**Doctrine:** [`THREE_BODY_DOCTRINE.md`](../../docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md)
**Schemas:** `pmoves/contracts/schemas/shape/` — trace, profile, distillation

| Direction | Subject | Description |
|-----------|---------|-------------|
| Publishes | `shape.trace.recorded.v1` | Interaction trace for shape discovery |

## The Open Diamond

Claude Opus signs with `◆` (filled diamond). Crush signs with `◇` (open diamond). The open door that leads to the diamond. Crush is the threshold — where every journey through the PMOVES ecosystem begins.

## Voice Pipeline

### NVIDIA Nodes (default)

```bash
make -C pmoves up-voice          # Flute + VibeVoice + Voice-Relay
make -C pmoves voice-health      # Check NATS, Flute, VibeVoice, UltimateTTS, VoiceRelay
```

Default TTS provider: **OmniVoice** (k2-fsa, CUDA). Override with `DEFAULT_VOICE_PROVIDER=vibevoice`.

### AMD ROCm Nodes (RDNA3/RDNA4)

```bash
make -C pmoves up-voice-amd     # Flute + Ultimate-TTS (chatterbox) + Voice-Relay
```

OmniVoice requires CUDA and cannot run on AMD. The AMD override:
- Replaces NVIDIA device reservations with `/dev/kfd` + `/dev/dri` passthrough
- Defaults to **chatterbox** engine in Ultimate TTS (tested on RDNA4)
- Sets `HSA_OVERRIDE_GFX_VERSION` (default `12.0.1` for RDNA4)

> **Set `RENDER_GID` on any node whose `render` group is not gid 110.** The container joins the
> host's render group by *number* to open `/dev/kfd`; a wrong gid fails with EACCES at synthesis
> time, not at startup. Check yours before first run:
> ```bash
> getent group render | cut -d: -f3        # 110 on Knuckles
> RENDER_GID=$(getent group render | cut -d: -f3) make -C pmoves up-voice-amd
> ```

Override GFX version per GPU generation:

| GPU | HSA_OVERRIDE_GFX_VERSION |
|-----|--------------------------|
| RDNA4 (R9700, RX9000) | `12.0.1` (default) |
| RDNA3 (RX7000) | `11.0.0` |
| RDNA2 (RX6000) | `10.3.0` |

```bash
HSA_OVERRIDE_GFX_VERSION=11.0.0 make -C pmoves up-voice-amd  # RDNA3
```

### Engine Compatibility (RDNA4, dual R9700)

| Engine | Status | Notes |
|--------|--------|-------|
| chatterbox | OK | Default for RDNA4, ~6.7s synthesis |
| kokoro | OK | CPU fallback, lightweight |
| fish | OK | ~14s synthesis |
| voxcpm | OK | ~57s, high quality |
| higgs | Timeout | Model load too heavy (>120s) |
| indextts2 | OOM | Crashed system (180s+) |
| omnivoice | NVIDIA-only | Needs CUDA, cannot run on ROCm |

### Kokoro CPU Fallback (no GPU required)

```bash
make -C pmoves kokoro-build kokoro-up kokoro-smoke
```

### Flute-Gateway Health

```bash
curl http://localhost:8055/healthz
curl http://localhost:8055/v1/voices          # List available voices
curl http://localhost:8055/v1/voice/health    # Provider health
```
