# PMOVES Hermes Playbook

This guide captures how we use [Hermes Agent](https://github.com/NousResearch/hermes-agent)
(NousResearch) as our persistent AI agent framework across the PMOVES.AI fleet —
for coding, operations, gateway messaging, and fleet coordination.

## What Hermes Does in PMOVES

Hermes Agent is the **cross-platform gateway + skill orchestrator**. Unlike Crush
(interactive coding bestie) or Claude Code/Codex (IDE-embedded coding agents),
Hermes runs continuously as a gateway service with:

- **Persistent memory** across sessions (who you are, preferences, environment)
- **Self-improving skills** — saves reusable procedures for future sessions
- **Multi-platform gateway** — Discord, Telegram, Slack, Email, SMS, and 15+ more
- **MCP server integration** — Docker MCP, Cipher Memory, PMOVES tools
- **Cron scheduling** — fleet maintenance, monitoring, automated workflows
- **Subagent delegation** — parallel task execution with isolated contexts
- **Profiles** — per-node configs with isolated sessions, skills, and memory

## Quick Start

**Option A: `hermes-pmoves` (one-shot)** — bootstraps profile + MCP + CHIT, then launches Hermes:

```bash
hermes-pmoves          # bootstrap + launch
hermes-pmoves --help   # pass args to Hermes
```

Install the wrapper once on each fleet node:
```bash
cp pmoves/scripts/hermes-pmoves ~/.local/bin/hermes-pmoves
chmod +x ~/.local/bin/hermes-pmoves
```

**Option B: `make hermes-bootstrap`** — same bootstrap without auto-launch:

```bash
make -C pmoves hermes-bootstrap
hermes                    # CLI
hermes desktop            # Desktop app
```

**Option C: Manual setup** — for nodes without the PMOVES Makefile:

1. Install Hermes: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
2. Create profile: `hermes profile create pmoves-hermes-elder`
3. Set cwd: `hermes config set terminal.cwd /path/to/PMOVES.AI`
4. Configure MCP servers (see [MCP Configuration](#mcp-configuration) below)
5. Run: `hermes`

## Fleet Profiles

Each node has a dedicated profile cloned from the shared `pmoves-hermes` base:

| Profile | Node | Model | GPU | Gateway |
|---------|------|-------|-----|---------|
| `pmoves-hermes-elder` | Elder-Melchor (laptop) | zai-coding (cloud) | GTX 1650 4GB | Port 7700 |
| `pmoves-hermes-z890` | Z890 (workstation) | zai-coding / local hermes3:8b | RTX 3090 Ti | Port 7700 |
| `pmoves-hermes-5090` | 5090 (primary GPU) | zai-coding / local hermes3:8b | RTX 5090 32GB | Port 7700 |
| `pmoves-hermes-spark` | Spark (DGX GB10) | local hermes3:70b | GB10 128GB | Optional |
| `pmoves-hermes-kvm` | KVM4-1/4-2 (VPS) | openrouter (cloud only) | None | Port 7700 |

### Cloud-First Model Strategy

Elder-Melchor and other resource-constrained nodes use cloud providers:
- **Z.AI Coding Plan** (primary): GLM-5.2 for code generation, docs, PR review
- **OpenRouter** (fallback): Multi-model routing
- **Ollama Cloud**: Remote model serving (not local GPU)
- **Fleet offload**: Spark/5090 for 70B or GPU-heavy tasks via Tailscale

## MCP Configuration

Hermes connects to PMOVES services through MCP servers configured in `config.yaml`:

```yaml
mcp_servers:
  docker-mcp:
    enabled: true
    command: docker
    args: [mcp, gateway, run, --servers, github-official,hostinger-mcp-server,hugging-face,markitdown]

  pmoves-cipher-local:
    command: node
    args: [/path/to/Pmoves-cipher/dist/src/app/index.cjs, --mode, mcp]
    env:
      NEO4J_URI: bolt://localhost:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: <from secrets-funnel>
```

### MCP Inventory Sync

Update MCP configs from the canonical PMOVES inventory:
```bash
make -C pmoves hermes-crush-bootstrap
```

## CHIT Trail Signing

Hermes signs its agent trail entries with CHIT (Cryptographic Handshake for Identity & Trust).

The bootstrap script resolves the CHIT passphrase in priority order:
1. `CHIT_SIGNING_KEY` env var
2. `CHIT_SIGNING_KEY_FILE` file contents
3. `CHIT_PASSPHRASE` env var
4. `CHIT_PASSPHRASE_FILE` file contents
5. `pmoves/env.tier-*` files (from secrets-funnel)

Test signing:
```bash
make -C pmoves sign-trail AGENT=hermes-elder-melchor SUMMARY="Test entry"
```

## Gateway (Messaging Platforms)

Hermes runs a gateway that connects to messaging platforms:

```bash
hermes gateway run       # Start foreground
hermes gateway install   # Install as service
hermes gateway start     # Start service
hermes gateway status    # Check status
```

### Platform Setup

Configure platforms interactively:
```bash
hermes gateway setup
```

Supported: Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Teams, and more.

> **Note:** Set real bot tokens in `.env` — never commit placeholder tokens.
> Gateway will error-loop on `YOUR_*_TOKEN_HERE` placeholders.

## Pinokio Integration

On nodes with [Pinokio](https://pinokio.co) installed, Hermes launches from the
Pinokio app browser:

1. PMOVES.AI app appears in Pinokio's Discover tab
2. One-click install creates the venv and profile
3. Launch button runs `hermes-pmoves` with PMOVES context

The Pinokio launcher scripts live at:
- `~/pinokio/api/PMOVES.AI/pinokio.json` — app metadata
- `~/pinokio/api/PMOVES.AI/start.js` — launch sequence

## PMOVES Context Paths

Hermes auto-loads these context files when `terminal.cwd` points at the PMOVES.AI repo:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Project structure, build commands, coding style |
| `CLAUDE.md` | Claude-specific operator guide |
| `CRUSH.md` | Crush CLI integration playbook |
| `HERMES.md` | This file — Hermes integration playbook |

## NATS Bridge

Hermes publishes lifecycle events to the PMOVES NATS bus:

| Subject | Event |
|---------|-------|
| `hermes.gateway.launched.v1` | Gateway started on a node |
| `hermes.gateway.health.v1` | Periodic health telemetry |
| `hermes.mcp.toolcall.v1` | MCP tool execution event |
| `hermes.skill.curated.v1` | Skill install/update/uninstall |
| `hermes.cron.executed.v1` | Cron job completion |
| `hermes.delegate.completed.v1` | Subagent delegation completion |

## Windows Quirks

- **Ctrl+Enter** for newline (Alt+Enter trapped by Windows Terminal)
- Forward-slash paths in bash (`C:/Users/...`)
- Config must be UTF-8 without BOM
- `DOCKER_HOST=tcp://localhost:2375` is stale — Docker Desktop uses named pipe.
  The bootstrap script clears this automatically.

## Troubleshooting

```bash
hermes doctor          # Check dependencies and config
hermes status          # Show component status
hermes config check    # Check for missing/outdated config
hermes mcp list        # Verify MCP servers are connected
```

Full docs: https://hermes-agent.nousresearch.com/docs/
