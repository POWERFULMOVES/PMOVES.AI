# DARKXSIDE Standalone Architecture

> **Last updated:** 2026-06-03
> **Mode:** TOPOLOGY_MODE=standalone | Sidecar deployment
> **Companion:** PMOVES_AI_CONFIG.promptinclude.md

## Overview
DARKXSIDE is PMOVES.AI's standalone sidecar mode — a single Agent Zero container
that operates without the full compose stack (NATS, TensorZero, Supabase, etc.).
It's designed for deployment on any device with Docker.

## Capability Matrix

| Capability | Standalone | Docked | Fleet |
|-----------|-----------|--------|-------|
| Agent Zero LLM (Ollama local) | ✅ | ✅ | ✅ |
| Agent Zero LLM (cloud GLM-5) | ✅ | ✅ | ✅ |
| CHIT signing | ⚠️ Advisory | ✅ Required | ✅ Required + trail |
| CHIT *_FILE secrets | ✅ | ✅ | ✅ |
| NATS JetStream | ❌ Disabled | ✅ | ✅ |
| TensorZero routing | ❌ | ✅ | ✅ |
| Supabase (local) | ❌ | ✅ | ✅ |
| Supabase (cloud) | ✅ Via env | ✅ | ✅ |
| MCP tools | ✅ Local only | ✅ Full | ✅ Full |
| Room/Stage model | ❌ N/A | ✅ | ✅ |
| Multi-agent orchestration | ❌ | ✅ | ✅ |
| Mini CLI | ✅ | ✅ | ✅ |

## CHIT 3-State Behavior Gradient

### State 1: Standalone (unsigned/advisory)
- CHIT_REQUIRE_SIGNATURE=false
- CHIT_DECRYPT_ANCHORS=false
- Secrets loaded from env.shared via CGP, but no signature verification
- *_FILE support works (Docker secrets mount)

### State 2: Docked (signed)
- CHIT_REQUIRE_SIGNATURE=true
- CHIT_DECRYPT_ANCHORS=true
- All secrets must be CHIT-signed
- NATS JetStream available for CGP distribution
- Transition: update sidecar.env, restart container

### State 3: Fleet (fully hardened)
- Everything in State 2, plus:
- Branch trail handshake required
- NATS auth enforced
- Graphiti memory integration
- Multi-room orchestration via P7

## Sidecar-to-Fleet Transition

### Prerequisites
- Compose stack running (make -C pmoves up)
- CHIT bundle exported with signing enabled
- NATS reachable from sidecar

### Steps
1. Set TOPOLOGY_MODE=docked in sidecar.env
2. Set CHIT_REQUIRE_SIGNATURE=true
3. Set CHIT_DECRYPT_ANCHORS=true
4. Set AGENTZERO_JETSTREAM=true
5. Run make -C pmoves chit-export (with signing)
6. Run make -C pmoves secrets-funnel
7. Switch agent profile to tensorzero
8. Restart container

### Rollback
Reverse steps 1-8. CHIT trails created in standalone mode
remain valid but unsigned — they'll be re-signed on next docked operation.

## Standalone SITREP Template

When a fresh DARKXSIDE session starts, check:

```bash
# 1. Container health
docker ps --filter name=agent-zero --format '{{.Status}}'

# 2. LLM connectivity
curl -s http://host.docker.internal:11434/api/tags | head -5

# 3. CHIT state
python3 -c "from pmoves.chit.codec import load_cgp; print('CGP entries:', len(load_cgp()))"

# 4. Secrets funnel status
make -C pmoves secrets-funnel 2>&1 | grep 'env.tier'

# 5. What's offline
echo 'NATS: disabled (JETSTREAM=false)'
echo 'TensorZero: unavailable (no compose)'
echo 'Supabase: ' $(grep SUPABASE_URL pmoves/env.shared | cut -d= -f2 | grep -q 'supabase-kong' && echo 'local only' || echo 'cloud')
```

## Submodule Relevance in Standalone

| Category | Submodules | Standalone Relevance |
|----------|-----------|-------------------|
| **Required** | PMOVES-Agent-Zero | Core agent runtime |
| **Required** | PMOVES-agents-md | Agent format spec |
| **Optional** | PMOVES-Archon | When docked |
| **Optional** | PMOVES-supabase | When docked with local Supabase |
| **Optional** | PMOVES-tensorzero | When docked |
| **Inactive** | PMOVES-n8n, PMOVES-BoTZ | Fleet-only services |
| **Inactive** | PMOVES-ClawZ, PMOVES-Danger-infra | Fleet-only infrastructure |
| **Inactive** | PMOVES-YT, media services | Fleet-only media pipeline |

## Environment Variables
See PMOVES_AI_CONFIG.promptinclude.md for the full variable reference.
Key standalone variables:

| Variable | Standalone Value | Purpose |
|----------|-----------------|---------|
| TOPOLOGY_MODE | standalone | Disables fleet features |
| AGENTZERO_JETSTREAM | false | Disables NATS | 
| CHIT_REQUIRE_SIGNATURE | false | Advisory mode |
| CHIT_DECRYPT_ANCHORS | false | No anchor verification |
| Ollama URL | host.docker.internal:11434 | Local LLM |
