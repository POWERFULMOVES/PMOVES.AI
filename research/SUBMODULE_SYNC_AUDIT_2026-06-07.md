# Submodule / Fork Sync Audit — 2026-06-07

Two-layer audit of the PMOVES.AI submodule fleet + POWERFULMOVES fork network, with
remediation status. Companion to `research/GHCR_TRIVY_CVE_INVENTORY_2026-06-05.md` (PR #1720).

## Why two layers

"Sync the submodules" is really three sequenced jobs:

1. **Layer 2 — forks behind their upstreams** (the CVE concern: "move to latest so we
   stop patching old CVEs"). Mechanism: `gh repo sync` / `fork-sync.yml`.
2. **Layer 1 — PMOVES.AI gitlinks behind their fork-main** (stale pins). Mechanism: a
   `chore(submodules): promote N pointers` commit — **only after** the forks advance.
3. **Dirty working trees** inside submodules (uncommitted content).

Doing Layer 1 before Layer 2 just re-pins stale commits, so order matters.

## Layer 2 — forks vs upstream (from `fork-sync.yml` dry-run, run 27094184397)

The **ahead** column is PMOVES hardening that a merge must preserve. `gh repo sync`
fast-forwards cleanly only when `ahead=0`; `ahead>0` forks need a reviewed merge/PR
(`fork-sync.yml` opens one and auto-skips on conflict).

| Fork | behind | ahead | Status |
|---|--:|--:|---|
| PMOVES-hermes-agent | 1183 | 0 | ✅ synced 2026-06-07 |
| PMOVES-A2UI | 479 | 0 | ✅ synced 2026-06-07 |
| PMOVES-E2B-Danger-Room | 172 | 0 | ✅ synced 2026-06-07 |
| PMOVES-project-pegaprox | 103 | 0 | ✅ synced 2026-06-07 |
| PMOVES-E2B-Danger-Room-Desktop | 55 | 0 | ✅ synced 2026-06-07 |
| PMOVES-FinceptTerminal | 50 | 0 | ✅ synced 2026-06-07 |
| PMOVES-E2b-Spells | 86 | 0 | ✅ synced 2026-06-07 |
| PMOVES-ClawRouter | 12 | 0 | ✅ synced 2026-06-07 |
| pmoves-e2b-mcp-server | 5 | 0 | ✅ synced 2026-06-07 |
| **PMOVES-ClawZ** | 7935 | 9 | 🔴 CRITICAL — manual merge |
| **PMOVES-supabase** | 2176 | 3 | 🔴 CRITICAL — manual merge |
| **PMOVES-Creator** | 1200 | 12 | 🔴 CRITICAL — manual merge |
| PMOVES-tensorzero | 958 | 1 | 🟡 ahead>0 — workflow PR |
| PMOVES-Wealth | 790 | 28 | 🔴 high-ahead — manual |
| Pmoves-Health-wger | 646 | 9 | 🟡 ahead>0 — workflow PR |
| PMOVES-a0-plugins | 343 | 1 | 🟡 ahead>0 — workflow PR |
| PMOVES-Archon | 193 | 15 | 🔴 build-image fork — manual (preserve hardening + CVE dep bumps) |
| PMOVES-Open-Notebook | 152 | 43 | 🔴 build-image fork — existing PR #14 |
| PMOVES-headscale | 138 | 5 | 🟡 ahead>0 — workflow PR |
| PMOVES-Agent-Zero | 116 | 34 | 🔴 high-ahead — manual |
| PMOVES-BotZ-gateway | 7 | 7 | 🟡 ahead>0 — workflow PR |
| Pmoves-hyperdimensions | 7 | 3 | 🟡 ahead>0 — workflow PR |
| PMOVES-llama-throughput-lab | 7 | 1 | 🟡 ahead>0 — workflow PR |
| PMOVES-Pinokio-Ultimate-TTS-Studio | 5 | 2 | 🟡 ahead>0 — workflow PR |
| PMOVES-AgentGym | 2 | 3 | 🟡 ahead>0 — workflow PR |
| PMOVES-autoresearch, LMRL-Gym, PMOVES-MiniMax-MCP, PMOVES-mike | — | — | ✅ already synced |

## Layer 1 — PMOVES.AI gitlinks behind fork-main (from `pmoves-submodule-fleet`)

Promote **after** forks advance. Worst stale pins: ClawZ 30967, Archon 1308,
Headscale 271, Agent-Zero 24, BoTZ 23, DoX 6, Wealth 6, autoresearch 5, AgentGym 2.
Several at behind=1. `skills/*` are merely un-initialized locally (not drift).

## Dirty working trees (need investigation before promotion)

- `PMOVES-DoX` (gitlink on a `dependabot/uv/...` branch commit — verify intended)
- `PMOVES-ToKenism-Multi`
- `Pmoves-cipher` (uncommitted content inside the submodule)

## Tooling fix landed this session

**PR #1733** — `fork-sync.yml` was running green but syncing nothing: it resolved fork
SHAs via `git/ref/refs/heads/<b>` (doubled `refs/` → 404), and `--jq '.object.sha'`
emitted the literal `null`, slipping past the empty-check and failing create-ref with
`sha=null` → `FAIL: branch creation` for every fork. Fixed to `git/ref/heads/<b>` +
explicit `null` rejection.

## Remaining blockers / runbook

- **App not installed on fork repos** — `fork-sync.yml` uses the PMOVES.AI GitHub App
  token, installed on PMOVES.AI but not the forks, so workflow-driven branch creation
  402/403s. **Durable fix:** Settings → Installations → PMOVES.AI → Configure →
  **All repositories**; ensure app permissions include Contents R/W, Pull requests R/W,
  Workflows R/W, Metadata R. Then the workflow self-serves on schedule.
- **Local `gh repo sync` needs `workflow` scope** — forks whose upstream delta touches
  `.github/workflows/` require `gh auth refresh -s workflow` (done 2026-06-07).
- **CRITICAL high-ahead forks** (ClawZ, supabase, Creator, Wealth, Agent-Zero, Archon,
  Open-Notebook) — manual, one-at-a-time merges that preserve PMOVES hardening; do NOT
  bulk-merge.

## Next actions

1. ☐ Operator: set PMOVES.AI App → All repositories (durable self-serve).
2. ☐ Re-run `fork-sync.yml` (dry_run=false) → reviewable PRs for 🟡 ahead>0 forks.
3. ☐ Manual upstream merges for 🔴 CRITICALs (preserve hardening; supersede hand-patched CVEs).
4. ☐ Layer-1: `chore(submodules): promote` PR once forks settle.
5. ☐ Resolve dirty trees (DoX/ToKenism-Multi/cipher).
