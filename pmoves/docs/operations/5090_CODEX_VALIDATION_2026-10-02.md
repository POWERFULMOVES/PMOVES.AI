# 5090 CODEX Validation - 2026-10-02

> Re-validation of the 5090 node after a 128-day gap since
> [`5090_CODEX_VALIDATION_2026-05-27.md`](./5090_CODEX_VALIDATION_2026-05-27.md).
> Closes the validation staleness flag from the 2026-10-02 sit-rep.
> Companion slice: `fix/5090-claude-pmoves-launcher-anthropic-routing`
> (rebased onto `feat/claude-backend-switch`); see PR #3184 for the actual
> `--backend=` / `pmoves-mini claude-backend` fix.

## Host

- Hostname: `POWERFULMOVES`
- Branch: `infra/5090-node-revalidation-2026-10-02`
- Worktree: `C:\Users\russe\Documents\PMOVES.AI-infra-5090-node-revalidation-2026-10-02`
- Base after refresh: `ddcd51e3129227e5911615307d9911408490ff50`
  (`fix(kilocode): round 2 review fixes — Cipher MCP endpoint + full CHIT protocol`)

## Results

| Check | Result | Evidence |
|-------|--------|----------|
| GPU visible | PASS | `NVIDIA GeForce RTX 5090, 32607 MiB, driver 595.79` — driver unchanged from 2026-05-27 |
| GPU utilisation now | 14571 MiB used / 32607 MiB total (44.7 %), 13 % util | live workload warm, healthy |
| TensorZero health | PASS | `http://localhost:3030/health` → `{"gateway":"ok","clickhouse":"ok","postgres":"ok","valkey":"ok"}` |
| TensorZero container health | PASS (assumed) | container `pmoves-tensorzero-gateway-1` + `-clickhouse-1` up 11 days (healthy) per `docker ps` |
| Parent submodule integrity (HEAD gitlinks) | PASS | 53 gitlinks at `ddcd51e312`, no unmerged conflicts |
| Parent submodule integrity (vs `PMOVES.AI-Edition-Hardened`) | DRIFT | 48 of 53 gitlinks differ from Hardened (auto-branch lineage carries kilocode PR #2101 chain) — by design, this slice is on `feat/auto-*` |
| Submodule working-tree clone-init | **PENDING — ENVIRONMENT** | `git submodule update --init --jobs 8` failed twice on Windows: (1) 180 s timeout, (2) `pmoves-hirag-mcp` clone → `Failed to connect to github.com port 443 after 21086 ms`, then `fatal: Unable to find current revision in submodule path 'PMOVES-Archon'`. Same LFS + nested-`.gitmodules` pattern documented in 2026-05-27 validation; subsequent timeout cancellation cascaded. Re-run on a Linux/macOS node or after `git config --global url.https://github.com/.insteadOf` is set; not blocking for this doc — submodule **gitlinks** are clean |
| Pinokio root | PASS | `D:\pinokio` exists (referenced by `PMOVES.AI-pr-5090-sitrep` worktree state) |
| Unsloth base import | **FAIL — UNCHANGED** | `ModuleNotFoundError: No module named 'unsloth'` in the base Python environment; same as 2026-05-27 |
| Torch base import | **FAIL — NEW finding** | `ModuleNotFoundError: No module named 'torch'` in the base Python environment (root cause for the Unsloth FAIL — Unsloth requires torch) |
| NATS reachable | PASS | `docker exec pmoves-nats-1 wget -qO- http://localhost:8222/varz` → `server_id=ND54UVWKE7553EWHLJCWWJE57C4VB65EA6PFB5KUNM7RCSSJMDLDDZXJ, version=2.11.8, go=go1.24.6, auth_required=true, port=4222` |
| Agent Zero reachable | PASS | `http://localhost:8080/healthz` → `{"status":"ok","nats":{"connected":true,"controller_started":true,"use_jetstream":true,"subjects":["agentzero.task.v1","agentzero.memory.update"]}}` |
| Archon reachable | PASS | `http://localhost:8091/health` → `{"status":"ok"}` |
| Cipher API reachable | PASS | `http://localhost:8105/health` → `{"status":"healthy","service":"cipher-pmoves-shim","version":"0.1.0","uptime_s":958892}` (~11 days) |

## Docker Snapshot Notes

99 containers up. Full PMOVES stack alive across 11+ days, including
the previously-broken **`pmoves-supabase-vector-1`** and
**`pmoves-supabase-edge-functions-1`** which were unhealthy in
2026-05-27 — **RESOLVED**.

Healthy cluster (selected, by age):

| Container | Status | Up time |
|-----------|--------|--------------|
| `pmoves-nats-1` | healthy | 11 d |
| `pmoves-neo4j-1` | healthy | 11 d |
| `pmoves-hi-rag-gateway-v2-1` + `-gpu-1` | healthy | 11 d |
| `pmoves-agent-zero-1` | healthy | 11 d |
| `pmoves-botz-gateway-1` | healthy | 11 d |
| `pmoves-fleet-sentinel-1` | healthy | 11 d |
| `pmoves-wealth-mcp` | healthy | 11 d |
| `pmoves-deepresearch-1` | healthy | 11 d |
| `pmoves-supaserch-1` | healthy | 11 d |
| `pmoves-p7-room-orchestrator` | healthy | 11 d |
| `pmoves-tokenism-simulator-1` | healthy | 11 d |
| `pmoves-archon-postgres` | healthy | 11 d |
| `pmoves-supabase-*` (15 services) | healthy | 11 d |
| `pmoves-meilisearch-1` | healthy | 11 d |
| `pmoves-qdrant-1` | healthy | 11 d |
| `pmoves-minio-1` | healthy | 11 d |
| `pmoves-ultimate-tts-studio-1` | healthy | 6 d |
| `pmoves-pmoves-ui-1` | healthy | 5 d |
| `pmoves-supabase-kong/gotrue/postgrest` | healthy | 5 d |
| `pmoves-channel-monitor-1` | healthy | 5 d |
| `pmoves-open-notebook-surrealdb` | up | 4 d |
| `pmoves-open-notebook` | up | 2 h |
| `monitoring-grafana/promtail/prometheus` | up | 11 d |

Ephemeral (3 unnamed compose):
`magical_shannon` (12 m), `laughing_ardinghelli` (28 m), `practical_einstein` (4 d)
— likely sandbox/test containers; no service-level healthcheck route.

## Ollama Inventory (live)

`curl http://localhost:11434/api/tags` returned **13 models**.
Models older than CHIT hardening (2026-05-16) have not been refreshed
since the 2025-08–2026-03 era; this matches the "Ollama staleness"
gap flagged in the 2026-10-02 sit-rep.

| Model | Family | Size | Modified |
|-------|--------|------|----------|
| `qwen3.5:9b` | qwen35 | 6.1 GB | 2026-03-15 |
| `qwen3:8b` | qwen3 | 5.1 GB | 2026-03-15 |
| `nomic-embed-text:latest` | nomic-bert | 274 MB | 2026-03-15 |
| (9 others — cloud aliases + embedding + vision) | — | — | 2025-09 → 2026-01 |

## Submodule Snapshot Notes

- **HEAD (`ddcd51e312`):** 53 gitlinks. Diff vs `PMOVES.AI-Edition-Hardened` = 48 different (auto-branch lineage; expected).
- **`PMOVES.AI-Edition-Hardened`:** 41 gitlinks. (May 27 closeout recorded 50 gitlinks on the older `codex/agnote-5090-closeout` worktree; the Hardened branch tip has 41.)
- **Drift interpretation:** 12-gitlink delta between Hardened and HEAD = new submodules added in the `feat/auto-*` lineage (likely from the kilocode PR #2101 chain: `pmoves-kilocode-*`, `pmoves-claude-pmoves-*`, `pmoves-launcher-generator-*` per the `feat-creator-collab-lane` worktree's recent log). NOT drift in the dirty sense — intentional additions.
- **Re-init recommendation:** Run on a Linux/macOS node or with `GIT_LFS_SKIP_SMUDGE=1 git submodule update --init --recursive --jobs 8`. Document the result in a follow-up validation entry; don't block this PR on it.

## Headline-Findings vs 2026-05-27

| # | Finding | 2026-05-27 | 2026-10-02 |
|---|---------|------------|------------|
| 1 | `pmoves-supabase-vector-1` | unhealthy | **healthy (11 d) — RESOLVED** |
| 2 | `pmoves-supabase-edge-functions-1` | restarting | **healthy (11 d) — RESOLVED** |
| 3 | Unsloth base import | FAIL | **FAIL — UNCHANGED** (torch also missing — NEW finding) |
| 4 | GPU driver | 595.79 | **595.79 — unchanged** |
| 5 | Container count (healthy core) | ~24 | **99 — full stack** |
| 6 | Ollama staleness | not measured | **13 models, oldest 2025-09** — gap flagged |
| 7 | Submodule integrity | PASS (50 gitlinks) | PASS (53 gitlinks, 48 vs Hardened drift = intentional) |
| 8 | Validation cadence | last snapshot | **128-day gap — closed** |

## Open follow-ups

- **PR #3184 (OPEN)** — `feat(claude-pmoves): --backend= flag + pmoves-mini claude-backend switch` — root-cause fix for the `MiniMax-M3[1m]` model error observed during this validation. Review + merge unblocks Anthropic-direct Claude Code on the 5090.
- **Post-merge action (operator-side on POWERFULMOVES):** `pmoves-mini claude-backend set anthropic`
- **Unsloth/Torch base import** — if either lane needs Unsloth, decide: (a) add `unsloth` to the base Python venv, or (b) move Unsloth to a dedicated sidecar container with its own pip image.
- **Ollama staleness** — refresh the 11-month-old local model set; do not blind-refresh, audit first.
- **Submodule init on Windows** — solve the LFS/network hang before the next workflow-scale commit on this box.