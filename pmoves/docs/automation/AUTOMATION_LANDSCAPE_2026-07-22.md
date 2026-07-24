# PMOVES Automation Landscape & Backlog — 2026-07-22

Read-only audit across four lenses (n8n currency, pipeline map, MCP/agents wiring, Activepieces/LinkedIn/make). Evidence-backed; every claim traces to a path/command. Feeds the prioritized backlog at the end.

> **Historical snapshot:** node state and external product versions below were
> observed on 2026-07-22. Revalidate them before operational changes. Repository
> statements in this revision were reconciled against current `main`.

## TL;DR

PMOVES automation is **three lanes, not one**: **n8n** (the built-out workflow engine — 32+ canonical pipelines, registry-synced, agent-wired over HTTP), **make/CI** (bring-up + scheduled maintenance crons), and a **Claude-native digest pair** (cloud routine + local Task Scheduler). A fourth the operator named — **Activepieces** (with LinkedIn) — has **zero repo footprint**; it's operator-external. "n8n has MCP and agents" is *agents-yes (HTTP), MCP-yes (merged on main; the audited node was simply stale), Archon-planned-only*.

---

## Lane 1 — n8n (the real workflow engine)

**Repo shape:** `PMOVES-n8n` submodule is a **wrapper/packaging repo**, not a source fork of `n8n-io/n8n`. It consumes the official Docker image, wrapped by `PMOVES-n8n/compose/n8n/Dockerfile`. Canonical workflows live in `PMOVES-n8n/workflows/` (**32+ flows**), mirrored to `pmoves/n8n/flows/` via `make n8n-sync-submodule-flows`. `pmoves/n8n-workflows/` (6 voice files) is a **stale legacy dir**, pre-submodule-reorg.

**Currency:**
- Current `main` pins the submodule at `abcb265`; the earlier `d2ff37b` one-commit gap is closed.
- **n8n core image pinned `n8nio/n8n:2.1.0` (~Dec 2025) → ~7 months stale.** CVE/patch gap for a public-facing engine. Scheduled bump, not a fire drill.
- **Version-skew bug:** `pmoves/docker-compose.n8n.yml` builds tag `pmoves/n8n:2.1.5-runtime` but its Dockerfile is `FROM n8nio/n8n:2.1.0`, while the `n8n-runners` sidecar pulls `n8nio/runners:2.1.5`. Core 2.1.0 vs runners 2.1.5 can break the task-broker protocol — internal-consistency bug, fix regardless of the staleness bump.

**Pipeline catalog** (32+ canonical; highlights): voice agents (discord/telegram/whatsapp + `voice_platform_router` + `voice_shared_functions`), `pmoves_audio_analysis`, `pmoves_video_analysis`, `pmoves_content_approval` + `approval_poller`, `pmoves_social_publisher` (Discord/Twitter/**LinkedIn**), `finance_firefly_sync` / `finance_monthly_to_cgp`, `health_wger_sync` / `health_weekly_to_cgp`, `pmoves_deepresearch_orchestrator`, `pmoves_jellyfin_watcher`, `pmoves_channel_monitor`, `pmoves_comfy_hub`/`_gen`, `echo_publisher`/`pmoves_echo_ingest`, `github_runner_autoscaler`, `github_webhook_processor`, `qwen/vibevoice/wan_to_cgp` webhooks, `yt_docs_sync_diff`, `langextract_orchestrator`, `pmoves_ingestion_hub`, `pmoves_notebook_content_feed`. Most STT→RAG→LLM voice flows call TensorZero + Hi-RAG + Supabase over HTTP; the `*_to_cgp` family builds `geometry.cgp.v1` envelopes.

**Deploy/ops (BUILT):** `n8n-bootstrap` (composite: `up-n8n` → `n8n-api-bootstrap` → `n8n-import-flows` → `n8n-activate-flows` → `n8n-sync-supabase-registry`). API-key bootstrap (`bootstrap_n8n_api.py`, SSRF-guarded), registry sync into Supabase `pmoves_core.n8n_workflow_registry`, canonical import/export (`import_repo_flows.py`/`export_repo_flows.py`), health checks.

## Lane 2 — make/CI

**Scheduled CI crons** (`.github/workflows/`): `agent-zero-upstream-check` (daily 06:00), `pat-health-check` (daily 12:00), `stale-branch-sweep` (daily 06:00), `submodule-update-check` (weekly Sun — tracks ~4 of ~25 submodules), `yt-dlp-bump` (weekly Mon), `python-images-toolchain-canary` (weekly Mon), `codeql` (weekly Fri). `integrations-ghcr` schedule commented out.

**Make automation targets:** n8n lifecycle (above); fleet/submodule (`submodule-sitrep`, `submodule-sync-*`, `submodule-promote`, `z890-verify`, `jetson-verify`); secrets (`secrets-funnel`); audit/evidence (`codex-audit`, `codex-parity-check`, `a0-plugins-check`, `*-evidence`). Note: `worktree-sitrep[-strict]` is **documented but not implemented**.

## Lane 3 — Claude-native digest pair

Cloud Claude routine (daily 13:00 UTC) → Gmail PR-audit digest; local Task Scheduler (`pmoves/scripts/daily_pmoves_digest.ps1` + `register_daily_digest_task.ps1`) → Discord worktree/branch state. Neither n8n nor make/CI — Claude Code's own routine mechanism.

## Lane 4 — Activepieces (+ LinkedIn): operator-external, but a viable fleet candidate

**Activepieces = zero repo footprint** — no submodule, no dir, no doc/plan/compose/env/git-history reference on any branch. Purely operator-external today. **LinkedIn** in-repo is only manual content (GTM docs `pmoves/docs/gtm/02_linkedin_package.md`, launch copy on `docs/socials-launch-copy`). The *in-repo* candidate for LinkedIn *automation* is n8n's `pmoves_social_publisher.json` (lists Discord/Twitter/LinkedIn) — activation state unverified.

**Why it was identified as a fleet candidate (external product check, 2026-07-22):** Activepieces was **MIT-licensed, open-source, self-hostable** (GitHub, Docker), so it fit the fork-as-submodule fleet pattern. It also exposed native MCP and AI-agent surfaces. Those are alternative automation surfaces, not evidence of a missing PMOVES MCP implementation: the PMOVES n8n/MCP work is already on `main`, while runtime activation still needs verification. Recheck licensing, current capabilities, and the LinkedIn connection method (official API vs unofficial) before making an adoption decision.

## Integration reality (the "n8n has MCP and agents" claim)

**Reconciled state:** the initial audit incorrectly described the MCP program as
missing and then as unmerged. The referenced work landed or was superseded on
`main`. Treat activation on any particular node as unverified until its checkout,
configuration, credentials, and live routes are checked.

| Link | State (in-tree) | Real state |
|---|---|---|
| n8n → Agent Zero | BUILT (HTTP `/events/publish`, 16 flows) | implementation present; runtime unverified |
| MCP servers (cipher/hirag/a0/comfy/notebooklm/observability/hermes) | wiring present on `main` | runtime activation must be verified per node |
| n8n ↔ Archon | not in workflows | `pmoves-n8n-archon-bridge` skill is design-doc; but `docs/workorder-archon-nats-2026-06-01` + archon-promote branches exist |
| Cipher usability | auth routes and bearer-forwarding fix are present on `main` | live container health and authentication remain node checks |

### MCP branches — MERGED OR SUPERSEDED (no branch revival)

**RE-CORRECTION (2026-07-22, triage-verified):** the "dropped work
orders" framing was itself wrong. The listed work is **merged or superseded on
main**. Status is based on merged-PR metadata and the identified replacement
path (for example, #1958 → #1960), not branch-tip ancestry. Squash merges do not
make the old branch tip an ancestor of `main`, so `ahead=N`,
`git merge-base --is-ancestor`, and `[gone]` are not merge evidence by
themselves.

| Branch | PR | Landed | Note |
|---|---|---|---|
| `fix/cipher-mcp-auth-header` | #2046 | 2026-07-10 | cipher bearer auth on main |
| `feat/hirag-mcp-bridge` | #1817 | 2026-06-15 | `pmoves-hirag-mcp` submodule on main |
| `feat/a0-mcp-toolkit` | #1856 | 2026-06-21 | A0 MCP toolkit on main |
| `feat/agent-zero-mcp-token-fleet` | #2057 | 2026-07-11 | `AGENT_ZERO_MCP_TOKEN` canonical |
| `feat/hermes-docker-mcp-toolkit` | #2108 | 2026-07-13 | TAC-tree Docker MCP |
| `feat/claude-mcp-cred-autoload` | #1987 | 2026-07-07 | `claude-pmoves` launcher |
| `feat/rooms-mcp-planned-apps` | #1894 | 2026-06-29 | cipher/nats/tailscale MCP apps in z890-infra room |
| `feat/add-comfy-mcp` | #2185 | 2026-07-21 | `"comfy"` block in mcp.json |
| `pr/feat/observability-mcp-servers` | #1361 | 2026-04-22 | 5 observability MCP servers (stale *local* ref only) |
| `feat/notebooklm-mcp-integration` | #1958 CLOSED → #1960 | 2026-07-04 | #1958 abandoned (committed node_modules); clean feature landed via #1960 — **do not revive #1958** |
| `feat/agent-registry-mcp-a2a-discovery` | — | — | already on main |

**Historical incident root cause:** at the time of the audit, the inspected node
was on `local/pmoves-hermes-z890-config`, 773 commits behind `main`; its
`.claude/mcp.json` predated the cipher-auth fix (#2046). Later handoff notes
reported a cutover to `main`, but that runtime state is not proven by this
repository document and must be checked live.

The repository-side recovery was #2184 plus the already-landed MCP work, not a
multi-PR branch revival. A node cutover still requires guarded checkout
reconciliation and live authentication checks; do not infer runtime success from
Git history alone.

## Division of labor

Documented in `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md`: n8n = "MCP Hub" (workflow automation + intended MCP tool exposure), Agent Zero = Primary orchestrator, Archon = MCP Server, make/CI = ops/bring-up layer. **Activepieces appears in NO architecture doc** — the n8n-vs-Activepieces-vs-make-vs-agents quadrant is the operator's mental model, not yet written down. Documentation gap.

## The #2181 audio-contract finding (grounded)

The review-thread claim that "n8n already reshapes `media.audio.analyzed.v1` → `analysis.audio.v1`" is **inaccurate**. The `Build CGP Envelope` node (in `pmoves_audio_analysis.json`) is webhook-triggered and synchronously HTTP-calls `media-audio:8082/process` — it does **not** subscribe to `media.audio.analyzed.v1`. **Three incompatible audio shapes coexist:**
1. Service `AudioProcessor.full()` raw payload (`emotion.emotions` nested, `transcription` not `transcript`, `features.rms_energy` flat, `file_path` not `audio_uri`, `diarization`, `task_id`/`timestamp`/…).
2. n8n `pmoves_audio_analysis.json`'s published `analysis.audio.v1` (a *third* shape — `asset_url`, `analysis.emotions`, …).
3. Registered `analysis.audio.v1` schema (top-level `emotions[]` required, `transcript.segments`, `features.global.rms`).

`media.audio.analyzed.v1` is **unregistered** in `topics.json`. `media-audio/server.py` exists only on branch `pr2181-hedge-trim`.

**Grounded fix (the "both"):** (a) register `media.audio.analyzed.v1` in `topics.json` + author a schema **from the real emitted payload** (no consumer to align to); (b) separately, reconcile the n8n flow's non-conformant `analysis.audio.v1` publish to the registered schema. These are two distinct contract-conformance fixes.

---

## Prioritized backlog

**P1 — correctness/security, small:**
1. **n8n version-skew** — reconcile `pmoves/n8n:2.1.5-runtime` tag / Dockerfile `FROM 2.1.0` / runners `2.1.5` to one aligned version (task-broker risk).
2. **#2181 audio contract (a)** — register `media.audio.analyzed.v1` + schema from the emitted payload; unblocks #2181's 2 deferred threads.

**P2 — hygiene/currency:**
3. **n8n core image bump** — `2.1.0` → current stable (test against `bootstrap_n8n_api.py` + Public-API import/activate; ~7mo of CVEs).
4. **n8n submodule currency check** — current `main` already pins `abcb265`; compare against the configured hardened branch before proposing another gitlink bump.
5. **#2181 audio contract (b)** — reconcile the n8n `pmoves_audio_analysis.json` `analysis.audio.v1` publish to the registered schema.
6. **Retire stale `pmoves/n8n-workflows/`** (6 legacy files) in favor of canonical `PMOVES-n8n/workflows/` + mirror.

**P3 — capability gaps (design-first):**
7. **n8n ↔ Archon** — implement the `pmoves-n8n-archon-bridge` design (add `up-archon` target, starter workflows, agent defs).
8. **n8n ↔ MCP** — verify each target node is on a current revision and exercise the merged MCP wiring end to end.
9. **Activepieces** — decide whether it becomes an in-repo fleet submodule or stays operator-external. Evaluate it for LinkedIn/connectors and operational fit, not as a substitute for supposedly missing MCP code. Recheck its current license, capabilities, and LinkedIn connection method before committing. Document the decision.
10. **Doc gap** — write the n8n/Activepieces/make-CI/agents division-of-labor into `PMOVES_COMPLETE_ARCHITECTURE.md`.
11. **`worktree-sitrep` target** — implement the documented-but-missing make target.
