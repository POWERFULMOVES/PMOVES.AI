# AGNOTE4482 SITREP — Quick Orientation

GRAPHITI_MARK: `PHI-4482-SITREP::QUICK-ORIENTATION`

> **For:** Any agent dropping into a PMOVES session cold (fresh start, VS Code restart, new node, Husk walk-in).
> **Rule:** Read this FIRST. It's pointers, not content. Follow the links.
> **Last refreshed:** 2026-04-01

---

## Where Am I?

Check your node:
```bash
hostname        # z890, pmoves-5090, pmoves-4090, kvm4-1, etc.
git branch      # what branch am I on?
git worktree list  # am I in a worktree?
```

## What's Happening Right Now?

| Question | Where to Look |
|----------|---------------|
| Who claimed what lane? | [`AGNOTE4482PHI.t1.md`](./AGNOTE4482PHI.t1.md) → Active Claim Register (bottom of section) |
| What's the merge/readiness state? | [`AGNOTE4482_SIGNOFF_CHECKLIST.md`](./AGNOTE4482_SIGNOFF_CHECKLIST.md) → Signoff Ledger |
| What shipped recently? | [`AGNOTE4482_ROADMAP_W1-W5.md`](./AGNOTE4482_ROADMAP_W1-W5.md) → Post-Audit Activity |
| What gaps are still open? | [`README.md`](./README.md) → Known Gaps (P0-P2) |
| What's the current sprint? | `pmoves/docs/NEXT_STEPS.md` |

## Fastest Health Check

```bash
# Container count + health
docker ps --format "table {{.Names}}\t{{.Status}}" | head -20

# Quick service health
make -C pmoves health-quick 2>/dev/null || curl -s http://localhost:8080/healthz

# Git state
git status -sb && git log --oneline -5
```

## Agent Definitions (Three-Body Solution)

PMOVES.AI uses Claude Code agent frontmatter (`.claude/agents/`) to enforce the
Three-Body Solution from AGNOTE4482PHI.t1.md at the tool level:

| Agent | Body | Can Edit? | Key Constraint |
|-------|------|-----------|----------------|
| `delivery-agent` | Delivery | Yes | `disallowedTools: EnterPlanMode` |
| `control-agent` | Control | No | `disallowedTools: Write, Edit, EnterPlanMode` |
| `memory-agent` | Memory | No | Cipher/CHIT skills only |
| `researcher` | — | No | Read-only, no sub-agents |
| `test-runner` | — | No | Worktree-isolated, pytest only |
| `pr-trimmer` | — | Yes | Worktree-isolated, PR review specialist |

Use: `claude --agent delivery-agent` or dispatch via `Agent({subagent_type: "delivery-agent"})`.

## Key Files (Read These, Not All of CLAUDE.md)

| Priority | File | Why |
|----------|------|-----|
| 1 | This file | Orientation |
| 2 | [`AGNOTE4482.md`](./AGNOTE4482.md) | Gateway — canonical pointers + latest audit |
| 3 | [`AGNOTE4482PHI.t1.md`](./AGNOTE4482PHI.t1.md) | Claim register — who's working on what |
| 4 | `.claude/agents/` | Agent definitions — Three-Body tool restrictions |
| 5 | `.claude/CLAUDE.md` | Full service catalog (heavy — skim Production Services) |
| 6 | `pmoves/docs/NEXT_STEPS.md` | Current sprint priorities |

## Cipher Marco/Polo

When you need cross-session context, use Cipher Memory via **skills with local fallback**.

```
# Marco (store intent) — use the skill
/cipher:store Agent orientation: current claims, active lanes, last session handoff

# Polo (retrieve by intent) — use the skill
/cipher:search what is currently claimed in AGNOTE4482
```

The key: **store with one phrasing, search with another**. When Cipher is fully online, its embedding model bridges the gap across phrasings.

**Intended MCP tools** (blocked — see known issue below):
- `pmoves_cipher_store` — persist findings, decisions, session summaries
- `pmoves_cipher_search` — recall context from prior sessions
- `pmoves_cipher_store_reasoning` — multi-step reasoning traces
- `pmoves_cipher_reasoning_patterns` — reusable reasoning patterns

> **Known issue (3-layer gap, 2026-04-01):**
> - **Layer 1 (skills):** Fixed — skills now use MCP-first with local MEMORY.md fallback
> - **Layer 2 (MCP client):** `pmoves-cipher-mcp/cipher_mcp/client.py` calls `POST /api/memory` and `GET /api/memory/search` — endpoints that don't exist
> - **Layer 3 (cipher-api):** `Pmoves-cipher/src/app/api/server.ts` registers `/api/message`, `/api/sessions`, `/api/mcp`, etc. but NO `/api/memory` routes
> - **Working path today:** Local MEMORY.md only. Skills auto-fallback when health check or MCP call fails.
> - **Fix:** Implement `/api/memory` CRUD routes in `Pmoves-cipher` submodule (separate PR)

## Cross-Node Context Gap

Claude's context is NOT consistent across z890/4090/5090. Each node may have:
- Different containers running
- Different worktrees checked out
- Different claim register state (if uncommitted changes exist)

**Always verify before assuming.** Run the health check above, then check the claim register.

## Agent Lanes Quick Reference

| Agent | Primary Node | Lane |
|-------|-------------|------|
| Z890-CLAUDE | z890 | Infra, fleet, compose, CI runners |
| 4090-CLAUDE | 4090 laptop | Provider cascade, Shift Crew, field testing |
| 5090-CLAUDE | 5090 | GPU, voice stack, submodule sync |
| CODEX-GPT5 | any | Docs, prospectus, creator control plane |
| KILOCODE-GLM | 5090 | GLM coding plan, vLLM, Proxmox |
| PMOVES-MINIMAX | any | Token plan overflow, writing, hyperdimensions |
| CLAUDE-OPUS | any | Architecture, self-review, convergence |

---

*If you're Husk and you just dropped in: welcome. Start at the top.*
