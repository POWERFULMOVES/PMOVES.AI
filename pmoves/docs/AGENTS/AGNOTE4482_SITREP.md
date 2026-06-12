# AGNOTE4482 SITREP — Quick Orientation

GRAPHITI_MARK: `PHI-4482-SITREP::QUICK-ORIENTATION`

> **For:** Any agent dropping into a PMOVES session cold (fresh start, VS Code restart, new node, Husk walk-in).
> **Rule:** Read this FIRST. It's pointers, not content. Follow the links.
> **Last refreshed:** 2026-06-11

---

## Where Am I?

Check your node:
```bash
hostname        # z890, pmoves-5090, pmoves-4090, kvm4-1, etc.
git branch      # what branch am I on?
git worktree list  # am I in a worktree?
```

### Branch Naming Convention

| Prefix | Use For |
|--------|----------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `infra/` | Infrastructure, CI/CD, DevOps |
| `docs/` | Documentation-only changes |
| `refactor/` | Code refactoring (no behavior change) |

**Workstream IDs**: Use `w1`–`w6` (from ROADMAP) or GitHub issue/PR number.
Example: `feat/w3-discord-classrooms`, `fix/1287-runner-loop`

**Forbidden**: `feature/` (use `feat/`), `pr/` (branches ≠ PRs), `p1/`–`p7/` (use workstream ID).


## What's Happening Right Now?

| Question | Where to Look |
|----------|---------------|
| Who claimed what lane? | [`AGNOTE4482PHI.t1.md`](./AGNOTE4482PHI.t1.md) → Active Claim Register (bottom of section) |
| What's the merge/readiness state? | [`AGNOTE4482_SIGNOFF_CHECKLIST.md`](./AGNOTE4482_SIGNOFF_CHECKLIST.md) → Signoff Ledger |
| What shipped recently? | [`AGNOTE4482_ROADMAP_W1-W5.md`](./AGNOTE4482_ROADMAP_W1-W5.md) → Post-Audit Activity |
| What gaps are still open? | [`README.md`](./README.md) → Known Gaps (P0-P2) |
| What's the current sprint? | `pmoves/docs/NEXT_STEPS.md` |

## Convergence Wave Index (Apr–Jun 2026)

Waves since last SITREP refresh (2026-04-01). Each links to its AGNOTE4482.md section.

| Wave | Date | Section | Key Deliverable |
|------|------|---------|----------------|
| Launch Prep | 2026-04-23 | §Launch Prep Audit | Runner restart fix, triage outcomes |
| MOF Architecture | 2026-04-23 | §MOF Architecture Convergence | `PMOVES_MOF_ARCHITECTURE.md` (337 lines) |
| Grand Convergence | 2026-04-23 | §Grand Convergence Wave | `PMOVES_GRAND_CONVERGENCE.md` (440 lines), 5-layer stack |
| P1/P2 Verification | 2026-04-24 | §P1/P2 Verification | Agent counts reconciled (15 agents, 67 docs) |
| Credential Audit | 2026-04-26 | §Credential & Naming-Drift | Signing identity cards, 5×5 trail invariant |
| NATS Auth P0 | 2026-04-24 | §NATS Auth P0 Resolution | Hardcoded credential defaults removed |
| 4090 Session | 2026-04-26 | §4090-CLAUDE Session | Coding plan alignment, KiloCode claw config |
| USB Provisioning | 2026-04-28 | §USB Provisioning Sweep | Tailscale SSH key distribution |
| W6 Convergence | 2026-04-27→05-02 | §W6 Convergence Wave | NATS defaults, chakra encoder, ToKenism hoist |
| Cinco de Mayo | 2026-05-05 | §PMOVES.AI Vision | Launch vision + next sprint framing |
| Fleet Modernization | 2026-05-09 | §CLAUDE.md Fleet Modernization | Claude.md Phase 2 continuation |
| Multilingual | 2026-05-11 | §Multilingual Translation | Translation tooling |
| Supply Chain | 2026-05-14 | `research/TANSTACK_SUPPLY_CHAIN_AUDIT` | 16 findings, 6 patched |
| SPARK Prep | 2026-05-15 | `AGNOTE-dgx-spark.md` | Model deploy script, profile reconciliation |
| MiniMax Token Plan | 2026-05-13 | §MiniMax Edition Integration | M2.7/M2.1 model suits, agent profile, NATS subjects, FlOO$ personas |
| CHIT Hardening | 2026-05-16 | §CHIT Hardening Sprint | 66-file audit, crypto consolidation, CHIT signing for 3 services, compose hardening, doc closure. **Signoff 37/37**. |
| Big Ball 5090 Codex | 2026-05-25→26 | §Big Ball 5090 CODEX Gap Closure | CHIT/ToKenism hardening, DoX hyperbolic projection, Tokenism settlement lanes, TensorZero 5090 health, submodule integrity |
| Big Ball Closeout | 2026-05-27 | §Big Ball 5090 CODEX Gap Closure | PR #1633 and #1638 merged, PR #1561 reviewed/merged, Tokenism activation pack started, 5090 validation snapshot recorded |
| Cole Medin Research | 2026-05-16 | `research/COLE_MEDIN_VIDEO_ANALYSIS.md` | 13 recent videos + 1827-item playlist scan, 5 P0/P1 integration recommendations for Nemo Claw, Archon, DGX Spark |
| Hardened Reconcile + Auto Mode | 2026-05-31 | §Hardened-Branch Reconciliation + Auto Mode Fleet Config | 38-submodule hardened audit, 5 security gaps closed (incl DoX CVSS 10.0 RCE), 15/17 reconciled, `AUTOMODE_FLEET_CONFIG.md` (**all nodes must apply locally**) |
| HERMES Agent Integration | 2026-06-04 | `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` | Full NousResearch Hermes Agent integration: room manifest, TAC tree, 6 node profiles (Z890, 5090, 4090, Spark, B850/RDNA4, KVM), agent registry/signature updates, operator skill, Three-Body agent definition. Local model mesh with Spark 70B primary. |
| Z890 Main-Infra Pass | 2026-06-04 | `AGNOTE4482PHI.t1.md` §Z890 Main-Infra Pass | SPARK-drafted PR cluster merged, CI-wide sha-pin outage fixed (#1698), `chit_manifest_merge.py` tooling (#1706/7), gateway port 8111 alignment → VPS deploy green |
| Z890 Fleet Fork-Sync + Governance | 2026-06-09→11 | `AGNOTE4482PHI.t1.md` §Fleet Fork-Sync Campaign | **All fork-sync drift cleared** (auto-tier + high-ahead Agent-Zero/hyperdimensions/Wealth + CRITICAL-huge ClawZ 8354c/Creator); **branch-protection automation** (31 forks protected, App Administration:RW validated, `branch-protection-sync.yml`); **supabase CRITICAL sync** (#1761 + TAC #1768, Kong gate passed); **Archon CI green** (lint #19 + E2E #20); space-agent public+protected |

> ~~**⚠️ AGNOTE4482.md section gaps:** Supply Chain, SPARK Prep, and CHIT Hardening were backfilled 2026-05-17.~~ All SITREP wave index entries now have corresponding §-sections.

## Fastest Health Check

```bash
# Container count + health
docker ps --format "table {{.Names}}\t{{.Status}}" | head -20

# Quick service health
make -C pmoves health-quick 2>/dev/null || curl -s http://localhost:8080/healthz

# Git state
git status -sb && git log --oneline -5

# PR check — warn if working on un-PR'd branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
  PR_COUNT=$(gh pr list --head "$BRANCH" --state open --json number --jq 'length' 2>/dev/null || echo "0")
  if [ "$PR_COUNT" -eq "0" ]; then
    echo "WARNING: working on un-PR'd branch: ${BRANCH}"
  fi
fi

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

## Current Closeout Truth (2026-05-27)

- Main includes PR #1633 (`fix: address PR 1603 review feedback`) and PR #1638 (`chore: advance transcribe submodule lfs cleanup`).
- Dependabot PR #1561 (`sigstore/cosign-installer` 4.1.1 -> 4.1.2 pinned action bump) was reviewed and merged with green checks.
- Tokenism settlement is still approval/deployment-gated, not production-live. The next artifact is `pmoves/docs/TOKENISM_PRODUCTION_ACTIVATION_PACK_2026-05-27.md`.
- 5090 validation evidence lives in `pmoves/docs/operations/5090_CODEX_VALIDATION_2026-05-27.md`.

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

## Node Capacity Quick Reference

Prior to PR #1378 (MOF architecture invariant, 2026-04-24), nodes were described by expertise
lane — Z890 "owned" infra, 4090 "owned" provider cascade, 5090 "owned" GPU/voice. That framing
was a pre-MOF mental model: it implied hard domain ownership and discouraged cross-node delegation.

After the Grand Convergence merge, every PMOVES node is a **pore in the MOF lattice** — capable
of running any PMOVES workload up to its physical capacity. Capacity class is **advisory**, not
gating: it tells you what a node can sustain under load, not what work it is permitted to do.

Cross-node delegation is the primary mechanism for matching workload to capacity:
1. Agent Zero `/mcp/*` — synchronous MCP tool call to a peer node
2. A2A `/.well-known/agent-card.json` — async agent-to-agent via the A2A spec (partially mounted; disabled by default)
3. NATS `agent.peer.heartbeat.v1` — presence/capability announcement (Phase D
   mutual-watching skill, not yet live)

The table below shows physical constraints and soft-priority notes per node.
No row is a hard lane assignment.

| Node | Capacity Class | Physical Constraints | Notes |
|------|----------------|---------------------|-------|
| Z890 (Sonic) | Workstation / multi-boot | 24GB VRAM; high core count; multi-OS | Most recent compose + CI runbook context |
| 5090 | Workstation / GPU-heavy | 32GB VRAM; CUDA primary | GPU inference workhorse; Opus 4.7 mirror active |
| 4090 laptop | Laptop / GPU-medium | 16GB VRAM; mobile; island-capable | Current operator node; provider proximity |
| SPARK (GB10 Blackwell) | Edge / unified-memory-large | 128GB unified memory; Blackwell | Island-mode capable; 3-phi relay candidate |
| Knuckles (AMD) | Workstation / CPU-heavy | 64GB RAM; AMD; no discrete GPU | Batch/CPU overflow; high-RAM non-GPU tasks |
| KVM4-1 | VPS / API-gateway | Network-primary; low VRAM | External API gateway; `self-hosted, kvm4` CI runner |
| KVM4-2 | VPS / data-storage | Storage-optimized | Data/storage tier |
| KVM2 | VPS / exit-proxy | Minimal compute; network-only | Exit proxy; RustDesk ScaleTail relay |
| (floating) | Inherits host node | Varies | CODEX-GPT5, CLAUDE-OPUS, PMOVES-MINIMAX — no fixed node |

---

## Restore Safety

> **Incident**: 2026-04-23 — file-level backup restore of AGNOTE4482_SIGNOFF_CHECKLIST.md silently overwrote 7 committed checkmarks (§1.1–1.3, §3.1–3.3). File-level restores bypass git merge/conflict detection.
>
> **Rule**: Before restoring ANY AGNOTE file from backup, run:
> ```bash
> git diff HEAD -- <file>
> ```
> Verify no checkmarks (`- [x]`) would be lost. If the backup is older than HEAD, the restore MUST be a manual merge, not a file copy.

*If you're Husk and you just dropped in: welcome. Start at the top.*
