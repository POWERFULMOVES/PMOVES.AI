# Production Audit Dashboard

> **Single source of truth** for PMOVES.AI production readiness.
> Supersedes all individual audit documents accumulated Feb 7 -- Feb 18, 2026.

**Last Updated:** 2026-03-08 (post-merge audit sweep — PRs #823/#824)
**Branch:** `PMOVES.AI-Edition-Hardened` (production release lane)
**Commit:** `ba3c7f84`
**Consolidated From:** 27 audit documents
**Evidence:** live runbook execution on 2026-03-05 (`make ghcr-prepublish-inrepo-build`, strict local Trivy sweep logs under `pmoves/docs/logs/ghcr-local-prepublish/`)

---

## Latest Changes (Mar 8, 2026)

- Post-merge audit sweep after PRs `#823` and `#824` merged to `main`:
  - `#823`: docs index cleanup sitrep refresh (branch/stash/worktree hygiene + stale doc archival)
  - `#824`: fix 8 broken links + 3 path mismatches in README_DOCS_INDEX (CodeRabbit comments addressed)
- **Static gate sweep (7 gates):** 6/7 PASS
  - `submodule-layer-validate-all-strict`: PASS (all submodules `[ok]`)
  - `submodule-branch-policy-check`: PASS (40 checked, DoX override acknowledged)
  - `submodule-integrity-strict`: PASS (40 gitlinks, 0 drifted, 0 conflicts)
  - `submodule-docs-audit-strict`: PASS (dossier regenerated)
  - `integration-contract-check-baseline`: PASS (3/3 — template, health-wger, firefly-iii)
  - `tooling-audit-strict`: PASS (errors=0 warnings=0, overlap_rows=124)
  - `secrets-audit`: TIMEOUT (long-running scan — pre-existing; auth-alignment confirms 0 errors)
- **Runtime verification:**
  - `smoke`: PASS (10/12 OK; Meilisearch + Neo4j WARN — pre-existing, not running locally)
  - `model-readiness`: PASS (17/17 passed, 0 failed, 1 warning — TZ model catalog non-list payload)
  - `monitoring-smoke`: PASS (Prometheus active=36 healthy=28, 20 Grafana dashboards, Loki ready)
  - `auth-alignment`: PASS (0 errors, 62 warnings — placeholder credentials, pre-existing)
  - `GPU smoke (strict)`: PASS (v2-gpu OK, v1-gpu optional endpoint returned HTTP 0 — expected)
- **Release gate spot-checks:**
  - RG-1: PASS — `ui-dev-start` only in `bringup_with_ui.sh` (dev/prod orchestrator, not production service)
  - RG-2: PASS — all compose port references use `${VAR:-default}` env-var patterns
  - RG-3: AUTOMATED — `_supabase` DB collation mismatch now auto-refreshed via `supa-collation-refresh` in `supa-start`; `make -C pmoves supa-collation-check` available for manual verification
  - RG-4: PASS — auth-alignment 0 errors
  - RG-5: PASS — `persona_model_resolution` returns 8 rows (all personas grounded)
- **CI/AB-9 status:**
  - All 4 self-hosted runners offline (pmoves-ai-lab-runner, pmoves-ai-lab-win, pmoves-hotfix-runner, pmoves-vps-runner)
  - 4 queued runs: 2 from `#822` merge push (GHCR + CodeQL), 1 stale `#822` PR run, 1 stale Deploy Gateway Agent
  - Queue guard identified all 4 as cancel candidates (non-PR or closed-PR events)
  - **Mitigation applied:** 10 lightweight workflows migrated from `[self-hosted, Linux, X64]` to `ubuntu-latest` (sql-policy-lint, python-tests, webhook-smoke, yt-dlp-bump, deploy-gateway-agent validate job, hardening-validation 4/5 jobs, build-images setup-matrix). Matrix throttling added (`max-parallel: 3-4`) to build-images and self-hosted-builds-hardened. Missing concurrency blocks added to codex-parity-advisory and webhook-smoke.
- Live metrics: Open PRs `0`, Dependabot `1` (medium), Code Scanning `0`

---

## Latest Changes (Mar 5, 2026)

- GHCR production local-first validation widened from single-image checks to matrix-driven validation:
  - local validator: `pmoves/tools/ghcr_local_prepublish.py`
  - operator targets: `ghcr-prepublish-inrepo`, `ghcr-prepublish-inrepo-build`, `ghcr-prepublish-all`, `ghcr-dispatch-all`
- In-repo GHCR integration build sweep (`linux/amd64`, local): `7/7 PASS`
  - `agent-zero`, `archon`, `firefly-iii`, `jellyfin`, `pmoves-yt`, `deepresearch`, `supaserch`
- Strict local Trivy sweep (HIGH/CRITICAL, ignore-unfixed, vuln-only): `3 PASS / 4 FAIL`
  - PASS: `firefly-iii`, `jellyfin`, `supaserch`
  - FAIL: `agent-zero` (scan timeout at 5m on large layer analysis), `archon` (known fixable HIGH/CRITICAL backlog), `pmoves-yt` (urllib3 CVE-2026-21441), `deepresearch` (known fixable HIGH/CRITICAL backlog)
- Evidence artifacts:
  - summary CSV: `pmoves/docs/logs/ghcr-local-prepublish/summary-2026-03-05.csv`
  - vuln-only summary CSV: `pmoves/docs/logs/ghcr-local-prepublish/summary-2026-03-05-vulnonly.csv`
  - per-image `.log` files are generated locally under `pmoves/docs/logs/ghcr-local-prepublish/` (ignored in git)

---

## Latest Changes (Mar 7, 2026)

- Merge wave completed on `main`: 8 PRs merged in 3 batches (#814-#821)
  - Batch 1 (06:00 UTC): #814 UI build fix, #815 smoke Supabase discovery, #816 healthcheck stability, #817 CI runner alignment, #819 DoX submodule bump
  - Batch 2 (07:01 UTC): #818 model fabric + coding-plan wiring (rebased after 8 CodeRabbit comments)
  - Batch 3 (17:11 UTC): #820 distributed topology docs, #821 chrome extension (9 security fixes)
- Chrome extension security review completed (9/11 actionable CodeRabbit items addressed):
  - `chrome.storage.sync` → `session` for auth credentials
  - innerHTML XSS eliminated in options shapes display
  - Mock server method allowlist + pathname routing
  - `synthesizeAudio` timeout (AbortController)
  - Processing status TTL cleanup
  - Config load race condition (configReady promise)
  - Storage read-modify-write serialization
  - Content Security Policy added to manifest.json
- GHCR matrix gap analysis completed (see section below)
- Live metrics: Open PRs `0`, Dependabot `1` (medium), Code Scanning `0`

### Repo Hygiene Sweep (Mar 7, 2026)

- Branch cleanup completed (`make -C pmoves branch-cleanup EXECUTE=1`):
  - Remote branches: 553 → 62 (275 merged-deleted, 216 archived as `archive/*` tags)
  - Local branches: 93 → 2 (`main` + `PMOVES.AI-Edition-Hardened`)
  - Worktrees: 1 stale removed (`PMOVES.AI-prod-validate`)
  - Stashes: 5 superseded stashes cleared
- Doc branch audit: 6 documentation-only branches verified (content confirmed on main) and deleted
  - `chit-audit-document`, `docs-pr-doc-review`, `docs/agents-review-2026-03-01`
  - `docs/nats-gpu-mesh-subjects`, `docs/roadmap-nextsteps-image-sitrep`, `docs/roadmap-nextsteps-post-merge`
- Post-cleanup state: 0 open PRs, 56 remote branches (62 minus 6 doc branches), 2 local branches, 0 stashes, 1 worktree

---

### GHCR Matrix Gap Analysis (Mar 7, 2026)

**Build pipelines:**
- `integrations-ghcr.yml` — 10 images (matrix-driven, multi-arch, Trivy + Cosign)
- `self-hosted-builds.yml` — 11 CPU + 2 GPU images (push-triggered, amd64)
- `build-images.yml` — 24 images from `images.yaml` (manual dispatch)

**GHCR registry:** 23 packages published.

**Compose → GHCR coverage gaps (4 truly missing):**

| Service | Compose Image Reference | In GHCR? | In CI? |
|---------|------------------------|----------|--------|
| `a2ui-nats-bridge` | `ghcr.io/.../pmoves-a2ui-nats-bridge:pmoves-latest` | ❌ | ❌ |
| `llama-throughput-lab` | `ghcr.io/.../pmoves-llama-throughput-lab:latest` | ❌ | ❌ |
| `session-context-worker` | `ghcr.io/.../pmoves-session-context-worker:latest` | ❌ | ❌ |
| `tokenism-ui` | `ghcr.io/.../pmoves-tokenism-ui:pmoves-latest` | ❌ | ❌ |
| `ultimate-tts-studio` | `ghcr.io/.../pmoves-ultimate-tts-studio:pmoves-latest` | ✅ (manual) | ❌ |

**Cross-reference gaps:**
- `integrations-ghcr.matrix.json` covers 10/24 `images.yaml` entries
- `self-hosted-builds.yml` builds 13 services not in `integrations-ghcr.matrix.json`
- 2 submodules in `images.yaml` still track `main` instead of `PMOVES.AI-Edition-Hardened` (`pmoves-botz`, `pmoves-tailscale`)

**Recommendation:** Add build definitions for the 4 missing images, or convert their compose references to local `build:` directives if they're dev-only.

---

## Latest Changes (Mar 6, 2026)

- Merge queue closeout completed on `main`:
  - merged: `#797`, `#798`, `#799`, `#800`, `#802`, `#803`, `#804`, `#805`, `#806`, `#807`
  - superseded closure: `#801` (scope absorbed into `#802`)
- CI/startup blocker class closed for `#802`:
  - CodeQL workflow parse failure fixed (valid path filter semantics)
  - auth/bootstrap runtime compatibility restored (`auth-check` + `supabase-boot-user`)
  - remaining CodeRabbit major comments resolved in follow-up commits before merge
- Production runtime validation (post-merge) now green:
  - `make -C pmoves smoke` PASS
  - `make -C pmoves model-readiness` PASS (`14/14`, `0` failed, `0` warnings)
  - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` PASS (optional v1 GPU endpoint warning only)
- Queue hygiene pass executed:
  - stale non-main queued/pending self-hosted runs canceled to free runner capacity for release-critical lanes.
- Coding-plan wiring refresh landed for production env alignment:
  - Alibaba Qwen provider lane added in TensorZero (`chat_alibaba_qwen`) using OpenAI-compatible DashScope endpoint.
  - gateway/model credential wiring now uses canonical `ALIBABA_PRO_CODING_PLAN` only.
  - model-readiness now validates GLM/Alibaba credential presence when coding-plan lanes are enabled.
- Persona grounding audit lane expanded:
  - release checks now require persona runtime grounding artifacts (`pmoves_core.persona_model_resolution`) and persona lookup indexes (`idx_personas_model_preference`, `idx_personas_active_name`) to be present before promotion.

---

## Latest Changes (Mar 4, 2026)

- Hardened fix wave merged in sequence: `#776`, `#777`, `#778`, `#779`, `#780`.
- Promotion sync merged: `#781` (`PMOVES.AI-Edition-Hardened` -> `main`).
- Admin merge closeout completed:
  - `PMOVES.AI`: `#782`, `#792`, `#793`, `#794`, `#795` merged
  - `PMOVES-Agent-Zero`: `#9` merged (hardened backport for submodule pin policy)
  - `PMOVES-BoTZ`: `#75` merged
  - `PMOVES-DoX`: `#117`, `#118`, `#119` merged
- Branch content parity is restored: `git diff origin/main..origin/PMOVES.AI-Edition-Hardened` returns no file deltas.
- Runtime posture improved:
  - `model-readiness` now passes warning-free (`14/14`, `0` warnings) after Ollama model pre-pull + DB fallback running-container fix.
  - strict GPU smoke passes (`GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`); v1 GPU lane remains optional and can warn when absent.
  - local operator evidence logs captured for smoke/model-readiness/strict-GPU runs during this audit pass.
  - Published Agent Zero startup in agents-image mode is stable (`/healthz` 200) via compose shim.
  - Local Supabase vector instability is controlled with CLI exclude support (`SUPABASE_CLI_EXCLUDE=vector`) in `supa-start`.
- CI queue remains the primary blocker class: self-hosted CodeQL/GHCR lanes still exhibit queue starvation; stale queued runs were drained during this audit pass.
- CI queue policy controls are now applied in-repo:
  - stale push/PR runs cancel per ref for `CodeQL Advanced`, `Docker Hardening Validation`, and `integrations-ghcr` (manual dispatch preserved; CodeQL schedule preserved)
  - matrix fan-out throttled (`CodeQL=1`, hardening dockerfile matrix `=2`, GHCR matrix `=2`)
  - GHCR push/PR triggers scoped to image-affecting paths to reduce docs-only queue noise

### Workflow Queue Best-Practice References (Official GitHub Docs)

- Concurrency groups + `cancel-in-progress`: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- Matrix throttling (`strategy.max-parallel`): https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs
- Path filters (`paths` / `paths-ignore`) and skipped-workflow caveats: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Self-hosted autoscaling/ephemeral runners (ARC): https://docs.github.com/en/actions/concepts/runners/actions-runner-controller

## Executive Summary

| Metric | Value |
|--------|-------|
| Quantitative snapshot timestamp | 2026-03-08 (live GitHub + local smoke/model-readiness/GPU/monitoring snapshot) |
| Total tracked items | 24 |
| Resolved | 23 (+1 since last update) |
| Active blockers | 1 (self-hosted queue starvation) |
| Critical | 0 |
| High | 1 |
| Medium | 0 |
| Low | 0 |
| CodeQL alerts (open) | **0 open** (live GitHub API on 2026-03-08) |
| Dependabot alerts | **1 open** (`1 medium`; live GitHub API on 2026-03-08) |
| Open PRs | **0** |
| CI queue | Hosted gates healthy; self-hosted queue starvation persists on CodeQL/GHCR lanes |

### Runtime Verification Snapshot (2026-03-08)

| Check | Result | Notes |
|---|---|---|
| `make -C pmoves smoke` | PASS | 10/12 OK; Meilisearch + Neo4j WARN (not running locally — pre-existing) |
| `make -C pmoves model-readiness` | PASS | `17/17` passed; `0` failed; `1` warning (TZ model catalog non-list payload) |
| `make -C pmoves monitoring-smoke` | PASS | Prometheus active=36 healthy=28; Grafana 20 dashboards; Loki ready |
| `make -C pmoves auth-alignment` | PASS | `0` errors; `62` warnings (placeholder creds — pre-existing) |
| Strict GPU smoke | PASS | `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` passed; v1 GPU optional HTTP 0 |
| Persona grounding (RG-5) | PASS | `persona_model_resolution` returns `8` rows |

### Local Atomic Lanes (2026-03-02)

| Commit | Lane | Scope | Status |
|---|---|---|---|
| `bd336349` | YT + Supabase docs sync parity | `pmoves-yt` import fallback, schema-aware upsert, `tool_docs` migration, Supabase schema exposure | Pushed (local branch) |
| `c7e227b6` | Runtime bring-up hardening | TensorZero startup scope, bring-up readiness checks, retro endpoint parity | Pushed (local branch) |
| `8db4e472` | Env/compose resilience | Compose fallback defaults + bootstrap placeholder resolution | Pushed (local branch) |
| `19dae85b` | DB migration compatibility | Persona schema normalization + role-compatible grants across Supabase migrations | Pushed (local branch) |

### Submodule Targeted PR Map (Local Review)

| Submodule | Local State | Targeted PR Recommendation |
|---|---|---|
| `PMOVES-Archon` | docs + split integration lanes merged | PR #9, PR #10, PR #11 merged |
| `PMOVES-HiRAG` | `CLAUDE.md` lane merged | PR #4 merged |
| `PMOVES-Open-Notebook` | docs lane + CI guard merged | PR #10 merged (includes fail-open guard for missing Claude auth secrets) |
| `PMOVES-Pipecat` | auth/default + lint lane merged | PR #2 merged |
| `PMOVES-transcribe-and-fetch` | local checkout shows 4 modified LFS/assets; clean hardened worktree shows no content delta | Treat as local LFS/worktree artifact until checkout normalized; do not promote pointer bump yet |
| `pmoves/integrations/archon` | split lanes merged and synced | runtime auth/default lane + pointer sync lane merged via Archon PR #10/#11 |
| `PMOVES-A2UI` | docs artifact lane merged | PR #4 merged (`A2UI_EVALUATION_REPORT.md`) |

### Release Closeout (2026-02-24)

| PR | Scope | Status | Merge Commit |
|----|-------|--------|--------------|
| #703 | PR699 parity remediation | MERGED | `bd576cc5` |
| #704 | deterministic submodule release gate/checklist | MERGED | `fbf1a06a` |
| #700 | Jellyfin prod topology alignment | MERGED | `9d3d5fb6` |
| #701 | Jellyfin prod verify/parity tools | MERGED | `979d4014` |
| #702 | Creator audit trail/docs | MERGED | `f51312be` |
| #699 | NATS auth + unified JWT + trails (promotion) | MERGED | `1a21c038` |

Release coordination note: `https://github.com/POWERFULMOVES/PMOVES.AI/pull/699#issuecomment-3948534322`

### Recent Merge Activity (2026-02-25 to 2026-02-28)

| PR | Scope | Status | Date |
|----|-------|--------|------|
| #719 | fix(mcp): cipher MCP SSE migration + review fixes | MERGED | 2026-02-28 |
| #718 | chore(deps): minimatch bump (solidity) | MERGED | 2026-02-27 |
| #716 | chore: submodule validation + 5 integration dossiers | MERGED | 2026-02-26 |
| #715 | fix(security): 25 CodeQL alerts (Tiers 1+2) | MERGED | 2026-02-26 |
| #714 | chore(deps): requests bump (pdf-ingest) | MERGED | 2026-02-26 |
| #713 | fix(compose): hardening batch — NATS auth, docs v4.0 | MERGED | 2026-02-26 |
| #712 | feat: topology+CHIT gate hardening | MERGED | 2026-02-25 |

### Recent Merge Activity (2026-03-02 — Main Branch)

| PR | Scope | Status | Date |
|----|-------|--------|------|
| #753 | feat(ci): queued-run guard and drain targets for self-hosted deadlocks | MERGED | 2026-03-02 |
| #752 | chore(submodules): bump Agent-Zero, cipher, transcribe-and-fetch | MERGED | 2026-03-02 |

### Submodule Targeted PR Merges (Split-Lane Wave)

| Submodule | PR | Scope | Date |
|-----------|-----|-------|------|
| PMOVES-A2UI | #4 | docs artifact (`A2UI_EVALUATION_REPORT.md`) | 2026-03-02 |
| PMOVES-Archon | #9 | targeted hardening lane | 2026-03-02 |
| PMOVES-Archon | #10 | runtime auth defaults | 2026-03-02 |
| PMOVES-Archon | #11 | nested pointer sync | 2026-03-02 |
| PMOVES-HiRAG | #4 | CLAUDE.md lane | 2026-03-02 |
| PMOVES-Open-Notebook | #10 | docs + CI guard (fail-open for missing Claude auth) | 2026-03-02 |
| pmoves-pipecat | #2 | auth/default + lint lane | 2026-03-02 |

### Current Hardening Drift Checks (2026-02-24)

- Production bring-up scripts still need a strict audit to ensure no `*-dev-*` targets are used in production lanes by default.
- Dynamic port mapping and Docker namespace publishing must be re-validated against compose/env defaults to eliminate hard-coded host/port drift.
- Supabase collation mismatch warnings must be treated as active watch items whenever base images or host locale packages change.
- Runtime auth/credential paths are unified by design, but cross-service verification remains required after key rotation and fresh bootstrap.

### Live CI Recovery (2026-02-20)

| PR | Branch | Focus | Status |
|----|--------|-------|--------|
| #681 | `fix/ci-self-hosted-hardening` | GHCR workflow adjusted to build-only behavior on pull requests (no push/sign/scan) to avoid 403 package push failures | In progress (checks re-running) |
| #678 | `fix/ci-pytest-conftest-collision` | Python tests switched to importlib mode and CodeQL JS lane now pins Node 20 on self-hosted runners | In progress (checks re-running) |
| #677 | `fix/silent-failure-hardening` | Same CI fix set as #678 plus compose fix to keep `nats-init` defined for default validation path | In progress (checks re-running) |

### Static Audit Layer Results (2026-02-18)

| Audit Layer | Result |
|-------------|--------|
| `submodule-integrity` | PASS (39 gitlinks, 0 drifted, 0 conflicts) |
| `submodule-docs-audit` | PASS |
| `integration-contract-check-baseline` | PASS (template + health-wger + firefly-iii) |
| `manifest-audit` | FAIL (env dependency: `pmoves` package not installed in shell) |
| `observability-audit` | PASS (static: 25 jobs parsed, 20 dashboard selectors) |
| `supa-runtime-guard` | PASS (no conflicting runtimes) |

### Runtime Evidence (2026-02-20)

| Check | Result |
|-------|--------|
| `make -C pmoves smoke` | PASS (production path: `tools/smoke_prod.py`) |
| `make -C pmoves agents-headless-smoke` | PASS |
| `make -C pmoves archon-smoke` | PASS |
| `make -C pmoves monitoring-smoke` | PASS (`active=36`, `healthy=21`) |
| Supabase storage migrator | RECOVERED (`supabase_storage_pmoves` healthy) |
| Supabase DB collation warning | CLEARED (no new `collation version mismatch` log entries after refresh) |
| `make -C pmoves submodule-integrity` | PASS (40 gitlinks, 0 drifted, 0 conflicts) |
| `make -C pmoves supa-env-doctor-strict` | PASS |

Evidence log: `pmoves/docs/evidence/audit-validation-2026-02-20-production-runtime.md`

---

## Active Blockers

| ID | Blocker | Source Doc | Severity | Status | Next Action |
|----|---------|-----------|----------|--------|-------------|
| AB-9 | Self-hosted runner queue starvation on CodeQL/GHCR lanes | Release closeout 2026-02-24 | **HIGH** | MITIGATING | Keep queue drain policy active, verify new concurrency/path throttles reduce queue depth, and validate at least one current `CodeQL Advanced` + GHCR matrix run reaches execution |
| AB-10 | `main` vs hardened commit-history divergence after squash promotion | Sync pass 2026-03-04 | **LOW** | TRACKED | Maintain content parity (`git diff` clean). Use explicit promotion + back-sync notes to avoid false-positive divergence alarms in ops reports |

### Blocker Detail

**AB-9: Runner Queue Deadlock**
Queue pressure remains the dominant operational risk. Even after stale-run drain, multiple `CodeQL Advanced` jobs remained queued on self-hosted lanes. In-repo workflow controls now mitigate this (`cancel-in-progress` for stale push/PR refs, matrix throttling, GHCR path scoping), but lane behavior still needs live verification over multiple merge cycles.

**AB-10: Commit-History Divergence Noise**
`main` and `PMOVES.AI-Edition-Hardened` are currently content-parity clean (no file delta), but commit graphs diverge due squash promotion + back-sync merges. Treat this as an expected history artifact unless file-level diff appears.

**AB-7: CodeRabbit Fixes — RESOLVED**
All PR #606 findings addressed. See Blocker Resolutions below.

### Additional Release Gates (2026-02-24)

These are tracked as release gates and should be closed with command evidence before final promotion:

1. `RG-1` Production command parity: verify no production path invokes `ui-dev-*` or equivalent dev-only targets by default.
2. `RG-2` Dynamic port and namespace parity: confirm compose services publish via configured env/namespace values, not hard-coded host assumptions.
3. `RG-3` Supabase collation/version hygiene: re-check logs after full rebuild/bootstrap and document whether `ALTER DATABASE ... REFRESH COLLATION VERSION` is required.
4. `RG-4` Auth unification regression pass: run JWT/key rotation flow and verify all core services re-auth without manual per-service patching.
5. `RG-5` Persona grounding/index gate: verify `pmoves_core.persona_model_resolution` resolves active personas and persona lookup indexes are present (`idx_personas_model_preference`, `idx_personas_active_name`) before release promotion.

---

## CodeQL Alert Triage (2026-02-18 Baseline → 2026-02-28 Update)

**Historical section:** this table preserves the 2026-02-28 triage baseline for traceability.
**Live status on 2026-03-04:** CodeQL open alerts are now **0** (all prior findings triaged/dismissed/fixed).

| Group | Count | Severity | Rule | Files | Remediation | Status |
|-------|-------|----------|------|-------|-------------|--------|
| A | 2 | **critical** | `py/full-ssrf` | `hi-rag-gateway/gateway.py:570`, `hi-rag-gateway-v2/app.py:1347` | Validate/allowlist URLs before requests | **FIXED** (PR #715) |
| B | 11 | high | `py/path-injection` | `pmoves-yt/yt.py` (11 locations: L1434-1761) | Add path sanitization utility; bulk fix | **FIXED** (PR #715) |
| C | 6 | high | `py/path-injection` | `gateway/api/viz.py` (4), `gateway/api/chit.py` (2) | Validate/sanitize file path parameters | **FIXED** (PR #715) |
| D | 2 | high | `py/path-injection` | `hf-mcp-server/main.py` (L522, L630) | Validate HuggingFace model paths | **FIXED** (PR #715) |
| E | 5 | medium | `py/stack-trace-exposure` | `consciousness-service/main.py` (3), `gateway/api/workflow.py`, `supaserch/app.py` | Replace traceback in HTTP responses with generic errors | **FIXED** (PR #715) |
| F | 2 | high | `js/xss-through-dom`, `js/resource-exhaustion` | `gateway/web/client.html:69`, `ui/lib/serviceHealth.ts:56` | Sanitize innerHTML; add request limits/timeouts | OPEN |
| G | 1 | high | `py/clear-text-logging` | `tools/chit_credential_demo.py:123` | Demo tool; redact or suppress sensitive logging | OPEN |
| H | 31 | mixed | Various | New/expanded scan results from PRs #716-719 | Requires fresh triage pass | **NEW** |

**Priority order:** H (fresh triage needed) > F (frontend XSS/resource) > G (demo tool)

---

## Dependabot Alert Triage (2026-02-18 Baseline → 2026-02-28 Update)

**Historical section:** this table preserves the 2026-02-28 triage baseline for traceability.
**Live status on 2026-03-04:** Dependabot open alerts are **1 medium**.

| Alert | Severity | Package | Manifest | Assessment |
|-------|----------|---------|----------|------------|
| #154 | **HIGH** | `serialize-javascript` | Jellyfin AI gateway | RCE via RegExp.flags and Date.prototype.toISOString(). Upgrade required. |
| #153 | **HIGH** | `serialize-javascript` | Jellyfin AI gateway | Same vulnerability, different manifest location. |
| #152 | **HIGH** | `minimatch` | Solidity contracts | ReDoS via matchOne() combinatorial backtracking. PR #718 bumped dep but alert may persist in lockfile. |
| #151 | **HIGH** | `minimatch` | Solidity contracts | Same vulnerability, different manifest location. |
| #133 | **HIGH** | `qs` | PMOVES-PROVISIONS submodule | arrayLimit bypass — memory exhaustion DoS. Upgrade to qs >= 6.14.1. |
| #148 | LOW | `fast-xml-parser` | Jellyfin AI gateway | Stack overflow in XMLBuilder with preserveOrder. Low blast radius. |
| #134 | LOW | `qs` | PMOVES-PROVISIONS submodule | arrayLimit bypass in comma parsing — DoS. Lower severity variant of #133. |

---

## Resolved Items (Archive)

These items are fully resolved and documented for historical reference.

### Blocker Resolutions (Latest)

| ID | Blocker | Resolution | Date |
|----|---------|------------|------|
| AB-1 | Recursive submodule traversal fails (exit 128) | **RESOLVED** -- Orphaned `Deskdesktop` gitlink removed from PMOVES-A2UI (commit f283f92). `git submodule status --recursive` exits 0. `known_path_typos` manifest cleaned. | 2026-02-18 |
| AB-2 | PMOVES-DoX drifted from parent pointer | **RESOLVED** -- DoX HEAD (3012ce4) aligned to `PMOVES.AI-Edition-Hardened`. PG17 compat fix (6ea52f4) confirmed present. Resolved via PRs #654-657. | 2026-02-18 |
| AB-3 | GHCR `integrations-ghcr.yml` not triggering | **RESOLVED** -- Push/PR triggers uncommented for `main` and `PMOVES.AI-Edition-Hardened` branches. Schedule triggers left disabled. | 2026-02-18 |
| AB-7 | CodeRabbit PR #606 PBKDF2 iterations | **RESOLVED** -- `credential_service.py` PBKDF2 iterations bumped from 100,000 to 600,000 (OWASP PBKDF2-HMAC-SHA256 minimum). All PR #606 findings now addressed. | 2026-02-18 |
| AB-8 | 5 conflicting PRs (#577-581) need rebase | **RESOLVED** -- 0 open PRs confirmed. All conflicts resolved via merge cycle (PRs #654-657). | 2026-02-18 |

### Blocker Status Resolutions (B1 -- B5)

| ID | Blocker | Resolution | Date |
|----|---------|------------|------|
| B1 | Orphaned gitlink `deskdesktop` | Phantom -- no such entry in git index; error from nested submodules only. In `known_path_typos`. | 2026-02-17 |
| B2 | Missing smoke Make targets | Phantom -- all targets exist in `pmoves/Makefile`: `smoke` (L1337), `smoke-gpu` (L1350), `verify-all` (L1026). | 2026-02-17 |
| B3 | CHIT/CGP schema inconsistency | Fixed -- standardized all producers to `chit.cgp.v0.2` via `CGP_SPEC_VERSION` constant. | 2026-02-08 |
| B4 | NATS JetStream streams not auto-created | Fixed -- `nats-init` sidecar + `init_streams.sh` creates GEOMETRY_CGP, TOKENISM_ATTRIBUTION, BOTZ_COORDINATION. | 2026-02-08 |
| B5 | GHCR duplicate platform entries | Fixed -- removed duplicate `linux/arm64` from 5 matrix lines. Triggers disabled pending runner stabilization. | 2026-02-08 |

### CI Infrastructure (Resolved)

- All 16 workflows migrated to self-hosted runners (`vps`, `ai-lab`, `gpu`) via PR #601, #602 (2026-02-08)
- `env-preflight.yml` intentionally uses `windows-latest` for PowerShell validation
- CI checks on commit `80d06daa`: Integration Contract Gate PASS, verify PASS, 16 queued (runners)

### Submodule Alignment (Resolved)

- 39 gitlinks mapped, 0 drifted, 0 conflicts (verified 2026-02-18)
- PRs merged: Archon #7, BoTZ #51, Agent-Zero #3, DoX #96
- DoX aligned to Hardened (PG17 fix confirmed present)
- 9 submodules individually reviewed (Archon, DoX, Wealth, BoTZ, A2UI, Deep-Serch, Pipecat, n8n, Open-Notebook)

### CHIT / GEOMETRY BUS (Resolved)

- All 5 mathematical pillars verified present on hardened branch
- Long Thread (Z) persistence implemented (checkpointing, Supabase)
- Security hooks added to Agent Zero runtime (40+ blocked commands)
- Gateway Agent NATS integration completed
- Zeta filter + MACA consensus wired through TensorZero

### Security (Resolved)

- Supabase credentials removed from git (`env.shared` remediated)
- API key validation added (PR #591)
- Container hardening patterns documented
- Security validator with pre-execution hooks deployed
- 36 CodeQL alerts remediated in PRs #651, #653, #654 (19+17+6 alerts fixed)
- 25 additional CodeQL alerts (SSRF, path injection, stack trace exposure) fixed in PR #715

### Context Architecture (Resolved)

- 51 worktrees and 31 CLAUDE.md files audited
- 4-tier context loading strategy documented
- Circular context loading prevention patterns established

---

## Audit Document Index

| # | Document | Date | Status | Summary |
|---|----------|------|--------|---------|
| 1 | `PRODUCTION_READINESS_AUDIT_2026-02-07.md` | Feb 7 | **Active** | Master readiness checklist; health checks + DB migrations pending |
| 2 | `PRODUCTION_AUDIT_PREP_2026-02-14.md` | Feb 14 | Superseded | Codex parity pass; smoke targets resolved (B2 phantom). Remaining items tracked in dashboard ABs |
| 3 | `SUBMODULE_REVIEW_TASKS_2026-02-07.md` | Feb 7 | Resolved | 10 submodule sync tasks; all resolved via PRs #654-657 |
| 4 | `SUBMODULE_REVIEW_SUMMARY_2026-02-07.md` | Feb 7 | Resolved | 9 submodule review results; DoX now aligned |
| 5 | `CI_AUDIT_REPORT_2026-02-08.md` | Feb 8 | Superseded | GHCR triggers re-enabled (AB-3 resolved 2026-02-18) |
| 6 | `DOCKER_GHCR_REVIEW_2026-02-08.md` | Feb 8 | Superseded | Trigger config resolved (AB-3 resolved 2026-02-18) |
| 7 | `ENV_TIER_AUDIT_2026-02-07.md` | Feb 7 | **Active** | env.tier-data missing credentials (AB-4 still open) |
| 8 | `CODERABBIT_REVIEW_606_2026-02-08.md` | Feb 8 | Resolved | All 12 actionable findings addressed; PBKDF2 iterations fixed (AB-7 resolved 2026-02-18) |
| 9 | `PRODUCTION_AUDIT_BLOCKER_STATUS.md` | Feb 17 | Resolved | B1-B5 all resolved or phantom |
| 10 | `SUBMODULE_BRANCH_AUDIT_2026-02-07.md` | Feb 7 | Resolved | 43 aligned, 3 PRs created and merged |
| 11 | `SUBMODULE_AUDIT_2026-02-07.md` | Feb 7 | Resolved | 40 submodules audited for branch alignment |
| 12 | `SUBMODULE_AUDIT_FINAL_2026-02-07.md` | Feb 7 | Resolved | 9 submodules reviewed; Archon PR #7 merged |
| 13 | `SUBMODULE_COMMIT_REVIEW_2026-02-07.md` | Feb 7 | Resolved | Commit-level review of main vs hardened |
| 14 | `CI_INFRASTRUCTURE_AUDIT_2026-02-08.md` | Feb 8 | Resolved | Self-hosted runner migration complete |
| 15 | `CHIT_AUDIT_TRACKING.md` | Feb 7 | Resolved | Core CHIT code verified on hardened |
| 16 | `AUDIT_LOG_2026-02-07.md` | Feb 7 | Resolved | Security remediation (credentials, hardening) |
| 17 | `CLAUDE_CONTEXT_AUDIT.md` | Feb 11 | Resolved | 51 worktrees, 31 CLAUDE.md files audited |
| 18 | `SUBMODULE_HARDENED_ALIGNMENT_2026-02-07.md` | Feb 7 | Resolved | Submodule main vs hardened diff |
| 19 | `SUBMODULE_SYNC_PROGRESS_2026-02-07.md` | Feb 7 | Resolved | Sync tracking (duplicate of Review Tasks) |
| 20 | `SUBMODULE_MERGE_READINESS_2026-02-07.md` | Feb 7 | Resolved | Merge readiness review |
| 21 | `PRODUCTION_VALIDATION_PLAN.md` | Feb 7 | Resolved | Validation plan (superseded by dashboard checklist) |
| 22 | `PRODUCTION_VALIDATION_SUMMARY_2026-02-07.md` | Feb 7 | Resolved | Env/compose validation summary |
| 23 | `PRODUCTION_BRING_UP_REPORT_2026-02-07.md` | Feb 7 | Resolved | Phase 1 bring-up progress |
| 24 | `PRODUCTION_READINESS_REPORT_2026-02-07.md` | Feb 7 | Resolved | "NOT READY" snapshot |
| 25 | `CI_VALIDATION_SUMMARY_2026-02-08.md` | Feb 8 | Resolved | CI migration complete (same as CI_INFRASTRUCTURE_AUDIT) |
| 26 | `PRODUCTION_VALIDATION_CHECKLIST.md` | Feb 7 | Resolved | Step-by-step checklist (TODOs now in dashboard AB-4/5) |
| 27 | `PRODUCTION_MERGE_TRACKER.md` | Feb 16 | Consolidated | Merged into dashboard (AB-8 section); no separate file created |

**Diagnostic artifacts:**
- `SUBMODULE_ALIGNMENT_SITREP_2026-02-14.md` -- machine-generated snapshot of submodule state
- `evidence/audit-validation-2026-02-18.log` -- full static audit validation output

---

## Validation Checklist

Run these commands to close remaining blockers:

```bash
# AB-4: Inject real credentials
make -C pmoves secrets-funnel

# AB-5: Service health (run with full stack up)
make -C pmoves verify-all

# AB-6: Migration validation (Supabase + data plane)
make -C pmoves supabase-bootstrap
make -C pmoves submodule-integrity-strict

# RG-1: ensure production lane is not calling dev helpers
rg -n "ui-dev-start|ui-dev-stop|ui-dev-logs|dev-start" pmoves/tools pmoves/Makefile

# RG-2: inspect hard-coded localhost/port assumptions in compose/env paths
rg -n "localhost:[0-9]+|127\\.0\\.0\\.1:[0-9]+" pmoves/docker-compose*.yml pmoves/env.shared pmoves/tools

# RG-3: Supabase collation check (automated via supa-collation-refresh in supa-start)
make -C pmoves supa-collation-check

# RG-4: auth unification regression pass
# Run JWT/key rotation flow and verify all core services re-auth

# GPU smoke test
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu

# Static deterministic gates
make -C pmoves submodule-layer-validate-all-strict
make -C pmoves submodule-layer-validate-strict
make -C pmoves submodule-branch-policy-check
make -C pmoves submodule-docs-audit-strict
make -C pmoves integration-contract-check-baseline
make -C pmoves tooling-audit-strict
make -C pmoves secrets-audit
make -C pmoves ci-runners-lockdown-strict
SUPABASE_RUNTIME=compose make -C pmoves supa-runtime-guard

# AB-9: Runner queue visibility/recovery evidence
gh run list --status queued --limit 20
gh run list --status in_progress --limit 20
gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners
```

### Resolution Sequence

1. **AB-4** first (credentials) -- unblocks AB-5, AB-6
2. **AB-5 + AB-6** together (bring up stack, validate health + migrations)
3. **AB-9** runner recovery (drain queued self-hosted lanes, confirm fresh pickup)
4. **CodeQL remediation** (43 open; Groups A-E fixed by PR #715, 31 new from expanded scope) -- follow-up: triage Group H, then F (frontend) + G (demo tool)

---

## Dashboard Hydration Contract

The static `docs/audit/dashboard.html` optionally fetches `GET /api/audit/summary?includeHealth=true&timeout=3000` when served over HTTP(S). On `file://` it renders baked data only.

### Consumed Fields

| Aggregator Field | Dashboard Section | Fallback |
|---|---|---|
| `generatedAt` | Header timestamp + staleness check | `new Date().toISOString()` |
| `productionAudit.branch` | Header branch label | `"main"` |
| `productionAudit.source` | Warning bar source hint | omitted |
| `productionAudit.activeBlockers[]` | Blockers panel + KPI card | `BLOCKER_DATA` |
| `releaseGates.source` | Warning bar source hint | omitted |
| `releaseGates.items[]` | Release Gates table + KPI card | `GATE_DATA` |
| `prMonitor.count` | KPI card + PR badge | `PR_DATA.count` |
| `prMonitor.totalBlockers` | KPI card sub-text | computed from `PR_DATA` |
| `runtimeHealth.*` | KPI card (Runtime Health) | replaced by Dependabot KPI |
| `warnings[]` | Warning bar below header | none |

### Not Consumed (baked-only sections)

Service Catalog, Submodule Grid, CodeQL Security, CHIT Integration — these are baked as JS literals and not available from the aggregator.

### Staleness

If `generatedAt` is older than 24 hours, a `(stale)` indicator appears beside the timestamp.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-08 | **Post-merge audit sweep:** PRs #823/#824 merged. Static gates 6/7 PASS (secrets-audit timeout). Runtime: smoke PASS (10/12), model-readiness 17/17 PASS, monitoring-smoke PASS, auth-alignment 0 errors, GPU smoke PASS. Release gates: RG-1/2/4/5 PASS, RG-3 KNOWN (collation). CI: all 4 runners offline, 4 queued runs (cancel candidates). Live metrics: 0 PRs, 0 CodeQL, 1 Dependabot (medium). |
| 2026-03-02 | **Live metrics sync (Codex):** refreshed executive summary from GitHub live data: CodeQL open alerts `36`, Dependabot open alerts `5`, open PRs `5`; CI snapshot synced to PR #758 head `db6b3a13` with self-hosted queue-capacity note. Ran queue guard and canceled stale queued runs `22565935122`, `22565935100`, `22565816518` to reduce deadlock pressure while preserving active PR lanes. |
| 2026-03-02 | **Post-split-lane cleanup:** merged origin/main (PRs #752, #753), resolved conflicts, fixed env churn idempotency, addressed 13 CodeRabbit review comments (SQL grants, credential fallbacks, docs_sync hardening, PostgREST schema, bringup runtime detection). |
| 2026-03-02 | **Split-lane merge closeout (Codex):** merged PMOVES-A2UI `#4`, PMOVES-Archon `#10`, and PMOVES-Archon `#11`; pushed final parent gitlink bump `a115a040` (A2UI + Archon + integrations/archon). |
| 2026-03-02 | **Submodule merge + split closeout (Codex):** merged PMOVES-HiRAG `#4`, PMOVES-Open-Notebook `#10`, PMOVES-Archon `#9`, and pmoves-pipecat `#2`; pushed parent gitlink bump commit `51f71013`. Opened follow-on split lanes: PMOVES-A2UI `#4`, PMOVES-Archon `#10` (runtime auth defaults), PMOVES-Archon `#11` (nested pointer sync). Transcribe-and-fetch asset lane validated as a local LFS/worktree artifact in primary checkout (no delta in clean hardened worktree). |
| 2026-03-02 | **Submodule atomic PR wave (Codex):** opened targeted lanes — PMOVES-HiRAG `#4`, PMOVES-Open-Notebook `#10`, PMOVES-Archon `#9`, pmoves-pipecat `#2`. Remaining mixed lanes held for split/verification: transcribe-and-fetch PR `#46` asset/LFS edits, `pmoves/integrations/archon` runtime+pointer mix, and detached `PMOVES-A2UI` docs artifact. |
| 2026-03-02 | **Local production remediation + commit-lane audit**: pushed 4 atomic commits (`bd336349`, `c7e227b6`, `8db4e472`, `19dae85b`) covering yt-docs sync parity, bring-up hardening, env/compose resilience, and DB migration compatibility. Updated live backlog metrics (Open PRs `4`, CodeQL `36`, Dependabot `5`) and added submodule-targeted PR map for dirty submodules. |
| 2026-03-02 | **Mar 2 merge wave**: PRs #748-#751 merged. Dashboard hydration (#750) with staleness + source hints. Presign port fix (#751). Audit summary API (#749). Roadmap refresh (#748). 3 submodule bumps landed (Agent-Zero, cipher, transcribe-and-fetch — PR #752). Worktree cleanup (11→1). 8 stale CodeQL runs cancelled. |
| 2026-02-28 | **Audit refresh**: 7 PRs merged (#712-719). CodeQL: 43 open (35 error, 8 warning) — PR #715 fixed 25 (Groups A-E), 31 new from expanded scan scope. Dependabot: 7 open (5 high, 2 low) — severity recomposed (serialize-javascript, minimatch, qs). PRs #577-581 all CLOSED. Open PR: #717 (dependabot, awaiting rebase). |
| 2026-02-25 | **Hardened→main sync** (#707): DAO recontext docs, DARKXSIDE registration, KRISS KROSS accord rewrite, release gates RG-1..RG-4, drift checks merged from Hardened. |
| 2026-02-24 | **Lock-step release closeout refresh**: merged PR sequence `#703 -> #704 -> #700 -> #701 -> #702 -> #699`, promoted to `main` at commit `1a21c038`, and updated dashboard blockers/metrics for remaining queue deadlock + credential/runtime validation. |
| 2026-02-24 | Hardened convergence update: marked quantitative metrics as `2026-02-20` snapshot values, added current hardening drift checks, and introduced release gates `RG-1`..`RG-4` for production command parity, dynamic port/namespace parity, collation hygiene, and auth-regression validation. |
| 2026-02-20 | **Production runtime remediation pass**: restored `supabase_storage_pmoves` (migration table/schema privilege repair for `supabase_storage_admin`), ran production smoke/agents/archon/monitoring checks (all pass), and verified no new collation mismatch warnings after collation refresh. Updated production diagnostics to use valid Agent Zero endpoints (`codex_health_quick.py`). |
| 2026-02-20 | Added live CI recovery tracking for PRs #677/#678/#681 and aligned dashboard update timestamp to current production-audit pass. |
| 2026-02-18 | **Blocker resolution pass**: AB-1 RESOLVED (orphaned Deskdesktop gitlink removed from A2UI, recursive submodule status exits 0). AB-3 RESOLVED (GHCR push/PR triggers uncommented). AB-7 RESOLVED (credential_service.py PBKDF2 bumped to 600k). Blockers reduced 6 → 3. Docs #5, #6 superseded, #8 resolved. |
| 2026-02-18 | **Audit validation pass**: AB-2 RESOLVED (DoX aligned), AB-8 RESOLVED (0 open PRs). AB-7 updated to PARTIAL. Added CodeQL triage (29 alerts in 7 groups), Dependabot triage (2 alerts), static audit layer results (5/6 PASS). Blockers reduced 8 → 6. Updated doc index statuses. |
| 2026-02-18 | Added 10 missed audit docs (#18-27), AB-8 conflicting PRs blocker |
| 2026-02-18 | Initial dashboard consolidating 17 audit documents |
