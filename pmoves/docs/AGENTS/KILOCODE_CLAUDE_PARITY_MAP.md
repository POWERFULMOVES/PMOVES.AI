# KiloCode ↔ Claude/Codex Parity Map

> **Command and capability mapping between KiloCode GLM, Claude Code, and Codex.**
> Mirror of `CODEX_CLAUDE_PARITY_MAP.md` — the canonical parity model.

**Last updated:** 2026-07-12
**Coverage:** KiloCode commands (`.kilo/command/`) ↔ Claude commands (`.claude/commands/`)

---

## Command Mapping

### Coordination & Protocol

| KiloCode Command | Claude Equivalent | Status | Notes |
|-----------------|-------------------|--------|-------|
| `/claim` | `/claim` (skill) | ✅ Parity | Both write to AGNOTE4482PHI.t1 |
| `/release` | `/release` (skill) | ✅ Parity | Both write RELEASE entry |
| `/sitrep` | `/sitrep` | ✅ Parity | Situation report |
| `/chit-sign` | `make sign-trail` | ✅ Parity | Trail signing |
| `/chit-encode` | `/chit-encode` (skill) | ✅ Parity | CGP packet encoding |

### Health & Diagnostics

| KiloCode Command | Claude Equivalent | Status | Notes |
|-----------------|-------------------|--------|-------|
| `/health` | `make -C pmoves health-quick` | ✅ Parity | Parallel health checks |
| `/smoke` | `make -C pmoves smoke` | ✅ Parity | GPU + core smoketests |
| `/deploy-up` | `make -C pmoves up` | ✅ Parity | Start services |

### Model Management

| KiloCode Command | Claude Equivalent | Status | Notes |
|-----------------|-------------------|--------|-------|
| `/model-populate` | `make -C pmoves model-pull` | ✅ Parity | Ollama model pull |
| `/vllm` | (no direct equivalent) | ⚠️ KiloCode-only | vLLM serving config |
| `/zai-mcp` | (no direct equivalent) | ⚠️ KiloCode-only | Z.AI MCP reference |

### Missing KiloCode Commands (in Claude but not KiloCode)

| Claude Command/Skill | Purpose | Priority |
|---------------------|---------|----------|
| `/chit-decode` | Decode CGP packets | P2 — referenced but missing |
| `/chit-bus` | GEOMETRY BUS operations | P2 — referenced but missing |
| `/worktree:create` | Create git worktree | P2 — use git directly |
| `/worktree:list` | List worktrees | P2 — `git worktree list` |
| `/pr-monitor` | PR monitoring | P2 — use `gh pr list` |
| `/docs-reconcile` | Doc freshness check | P2 — `make docs-reconcile-check` |

---

## MCP Server Parity

| MCP Server | Claude Code | KiloCode | Gap |
|------------|-------------|----------|-----|
| `pmoves-cipher` | ✅ | ✅ | — (resolved this PR) |
| `docker` | ✅ | ✅ | — |
| `tailscale` | ✅ | ✅ | — (resolved this PR) |
| `hostinger-mcp` | ✅ | ❌ | P2 — low priority for dev |
| `cloudflare` | ✅ | ❌ | P2 — deploy-only |
| `huggingface` | ✅ | ✅ | — (resolved this PR) |
| `pmoves-supabase` | ✅ | ❌ | P1 — data-plane queries |
| `supabase-db` | ✅ | ❌ | P2 — schema/migration |
| `pmoves-nats-fleet` | ✅ | ❌ | P1 — cross-node NATS |
| `zai-vision` | ❌ | ✅ | KiloCode-only (GLM-native) |
| `zai-web-search` | ❌ | ✅ | KiloCode-only (GLM-native) |
| `zai-web-reader` | ❌ | ✅ | KiloCode-only (GLM-native) |
| `zai-zread` | ❌ | ✅ | KiloCode-only (GLM-native) |

---

## Model Routing Parity

| Feature | Claude Code | Codex | KiloCode GLM |
|---------|-------------|-------|-------------|
| TensorZero function | `agent_zero` | `coding_codex` | `coding_kilocode` ✅ |
| Primary model weight | 0.6 (opus) | 1.0 (codex) | 0.8 (glm-5-turbo) ✅ |
| Provider cascade | ✅ (ClawZ) | ✅ | ✅ `kilocode_provider_cascade.yaml` |
| Model suit | ✅ (claude-*) | ✅ | ✅ `kilo-auto-balanced.yaml` |
| Agent profile | ✅ | ✅ | ✅ `kilocode_glm.yaml` |
| Lane classifier | `coding_plan` | `coding_plan` | `coding_plan` ✅ |

---

## Permission Parity

| Feature | Claude Code | KiloCode | Gap |
|---------|-------------|----------|-----|
| Bash allow list | ~200 patterns | blanket `allow` | ⚠️ Less granular |
| Damage-control hooks | ✅ 10+ hooks | ❌ | P1 — no hooks |
| Edit/Write pre-checks | ✅ | ❌ | P1 — no pre-edit safety |
| Trail signing hooks | ✅ PostToolUse | ❌ | P1 — manual only |
| MCP permissions | per-tool | per-server wildcard | Functionally equivalent |
| Browser permission | ✅ | ✅ | — (resolved this PR) |

---

## Fleet Citizenship Parity

| Feature | Claude Code | Codex | KiloCode GLM |
|---------|-------------|-------|-------------|
| KRISS KROSS signed | ✅ | ✅ | ✅ (this PR) |
| Operator home | ✅ | ✅ | ✅ `KILOCODE_OPERATOR_HOME.md` |
| Parity map | ✅ | ✅ | ✅ This file |
| Agent registry (full) | ✅ | ✅ | ⚠️ external_contributor only |
| Cipher memory map | ✅ | ✅ | ❌ P1 — pending |
| Persona playbook | ✅ | ✅ | ❌ P2 — pending |
| Makefile targets | ✅ `codex-*` | ✅ | ❌ P2 — pending `kilo-*` |
| Claim/release cycles | ~60+ | ~30+ | 1 (PR #1151) |

---

## Three-Body Role Declaration

KiloCode GLM defaults to **Delivery Body**:

```
Three-body: delivery=KILOCODE-GLM, control=DARKXSIDE, memory=this trail.
```

When KiloCode is the only active agent on a branch, it may temporarily serve all three roles but must declare this:

```
Three-body: delivery+control=KILOCODE-GLM (solo), memory=this trail.
```

---

## ACK

- Agent: `KILOCODE-GLM`
- Signature: `ACK::KILOCODE-GLM::PARITY-MAP`
- Timestamp: 2026-07-12
- DARKXSIDE ✦ witness
