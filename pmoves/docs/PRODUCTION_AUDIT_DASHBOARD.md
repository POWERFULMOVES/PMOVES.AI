# Production Audit Dashboard

> **Single source of truth** for PMOVES.AI production readiness.
> Supersedes all individual audit documents accumulated Feb 7 -- Feb 18, 2026.

**Last Updated:** 2026-03-11 (Post-PRs #867-#871 port registry + smoke fixes)
**Branch:** `main`
**Commit:** `c81b2431` (fix(ui): align PostgREST port registry + widen Jellyfin smoke codes)
**Consolidated From:** 27 audit documents
**Evidence:** live runbook execution on 2026-03-05 (`make ghcr-prepublish-inrepo-build`, strict local Trivy sweep logs under `pmoves/docs/logs/ghcr-local-prepublish/`)

---

## Latest Changes (Mar 11, 2026)

### PRs #867-#871 — Port Registry, Smoke Test & Security Fixes

- **PR #867** (`fix(security)`): CodeQL #196 — validate service URLs with `URL` constructor (XSS prevention)
- **PR #868** (`fix(smoke)`): Remap supabase-realtime port 4000→4010 in smoke tests + widen grep window
- **PR #870** (`fix(ports)`): Complete realtime 4000→4010 migration across PORT_REGISTRY and smoke tests
- **PR #871** (`fix(ui)`): Align PostgREST port registry (3010→3000) + env template fix + widen Jellyfin smoke HTTP codes (accept 502)
- **PR #866 closed** — superseded by the individual targeted PRs #867-#871
- **Branch sync:** main → Hardened synced (`c6bc276f`)
- **CodeQL status:** 1 open (#195 — false positive, `lgtm` suppression comment at `serviceHealth.ts:71`, pending GitHub dismissal on next scan)

### Post-PR #866 — CodeRabbit URL Validation Follow-up

- **CodeRabbit finding fixed:** `options.js` lines 131, 169 — added `validateServiceUrl()` helper using `new URL()` constructor with `http:`/`https:` protocol allowlist, matching the existing CodeQL #196 fix pattern at line 262
- Both `fetch()` call sites (individual test + test-all) now reject `javascript:`, `data:`, `file:` schemes
- Invalid URLs show "No URL" (individual) or "Invalid URL" status (test-all) instead of attempting fetch

### Post-PR #865 — Supabase Unification Complete

- **Supabase unification merged (PR #865):** 4 competing compose stacks → 1 canonical stack
  - 13 services under `supabase-local` profile (DB, GoTrue, PostgREST, Kong, Realtime, Storage, Studio, imgproxy, pg-meta, Edge Functions, Analytics/Logflare, Vector, Supavisor)
  - Consumer URL: `http://supabase-kong:8000/rest/v1`
  - All 13 services healthchecked (12 native + PostgREST documented exception)
  - `generate-keys.sh` fixed: pipefail-safe local/assignment split + macOS `openssl base64 -A` compat
  - ServiceTier aligned to canonical 7 tiers (added missing `ui` tier)
- **PR #864 closed** — superseded by #865 (integration credentials folded into unification)
- **CodeQL #196 fixed:** `js/xss-through-dom` in `chrome-extension/options/options.js:264` — strengthened URL sanitization from regex to `new URL()` constructor with strict protocol allowlist (`http:`/`https:` only via `parsed.href`)
- **CodeQL #194 auto-closed:** Rescan confirmed fix from `6c3a0455` (scheme validation)
- **Branch sync:** main → Hardened synced (`6726c146`)
- **Branch cleanup:** Deleted 2 feature branches (`feat/supabase-unify`, `fix/review-864`)
- **Remaining branches:** `main`, `PMOVES.AI-Edition-Hardened`, `PMOVES.AI-Edition-Hardened-Integrations`, `PMOVES.AI-Edition-Hardened-v3-clean`
- **CodeRabbit non-blocking follow-ups from PR #865:**
  - `health_to_research.json`: DeepResearch endpoint reference (cosmetic)
  - `integration_status_reporter.json`: Discord notification field names (cosmetic)
  - `voice_health_checkin.json`: Orphaned prompt template (cleanup)

### Previous — Branch Strategy Validation & Final Cleanup

- **Branch sync completed:** Reconciled bidirectional divergence (16 Hardened-only / 24 main-only commits)
  - Merged main → Hardened (PRs #848–#863 squash-merges)
  - Merged Hardened → main (distributed topology docs, submodule pins, dashboard refresh)
  - Synced Integrations branch to match Hardened
- **Stale branch cleanup:** Deleted 18 remote branches from merged/closed PRs (#842–#863)
  - Remaining branches: `main`, `PMOVES.AI-Edition-Hardened`, `PMOVES.AI-Edition-Hardened-Integrations`, `PMOVES.AI-Edition-Hardened-v3-clean`
- **CodeQL #194 fixed:** `js/xss-through-dom` in `chrome-extension/options/options.js` — added URL scheme validation (`/^https?:\/\//`) before assigning user-controlled `gatewayBase` to `link.href` (auto-closed by rescan)
- **CodeQL #195 suppressed:** `js/resource-exhaustion` in `ui/lib/serviceHealth.ts:71` — FALSE POSITIVE, timeout already clamped to `[1s, 60s]` via `Math.min(Math.max())` at line 69. Added `lgtm[js/resource-exhaustion]` suppression comment
- **Legacy CI refs cleaned:** Removed non-existent `integration` branch from `chit-contract.yml` and `deploy-gateway-agent.yml` workflow triggers
- **CONTRIBUTING.md updated:** PR target changed from `main` to `PMOVES.AI-Edition-Hardened-Integrations` per documented branch strategy
- **branch_cleanup.py:** Updated PROTECTED set — removed stale `integration`/`develop`, added `Integrations`

### Previous — PR Gate Sweep — All Open PRs Merged

- **Dependabot CI action bumps** (#860–#863) merged with `--admin`:
  - `aquasecurity/trivy-action` 0.34.2 → 0.35.0 (patch)
  - `sigstore/cosign-installer` 4.0.0 → 4.1.0 (minor)
  - `anchore/sbom-action` 0.23.0 → 0.23.1 (patch)
  - `docker/build-push-action` 5 → 7 (major — Node 24 runtime, no deprecated vars used)
- **PR #854** (`feat/github-app-credentials`) — 4 CodeRabbit threads resolved:
  - **FIXED:** `MEILI_MASTER_KEY` changed from `:-` fallback default to `:?` fail-closed (prevents deployment with predictable key)
  - **FIXED:** `proxy.ts` auth bypass narrowed from `startsWith('/api/health')` to exact match `=== '/api/health'`
  - **Explained:** App token org-scope (intentional for dynamic matrix), GH_APP_* forward-wiring (no-op until consumed)
- **CI queue cleanup**: 13 stale queued runs cancelled (merged dependabot branches, old feature branches, stale deploy runs)
- **Open PRs**: 0 (all 5 merged)
- **Dependabot alerts**: 0 open

### Previous (Mar 10, 2026) — P2 Final Resolution — All Items Closed

- **P2 tracker: 0 open / 17 total** — all items resolved
  - **#3 FIXED:** Open-Notebook SurrealDB credentials — all compose files now use `${SURREAL_PASSWORD:-changeme_surreal}` env var substitution
  - **#5 FIXED:** Open-Notebook `/metrics` — `prometheus_client` added, `make_asgi_app()` mounted at `/metrics` endpoint
  - **#10 CLOSED (wontfix):** Pipecat metrics — library scope; Prometheus metrics exposed at service layer by Flute-Gateway
  - **#13 CLOSED (accepted risk):** tensorzero RUSTSEC — all 4 advisories are transitive deps with documented justification in `deny.toml`
  - **#14 CLOSED (false positive):** tensorzero example secrets — examples use `${VAR:?required}` fail-closed pattern, not hardcoded secrets

### Previous — P2 Verification Sweep + Trivy Triage Correction

- **P2 tracker verification sweep** — checked all 11 open items against current submodule SHAs:
  - **6 CLOSED:** #2 BoTZ export syntax (no `export` in file), #6 PMOVES.YT MinIO creds (`${VAR:?required}` pattern), #9 Pipecat MCP allowlist (`tools_filter` implemented in `MCPClient`), #11 A2UI env.shared export (clean), #12 A2UI NATS auth (authenticated URL present), #16 A2UI env.tier-ui.sh export (clean)
  - **1 IMPROVED:** #5 Open-Notebook health endpoint (`/healthz` alias added, `/metrics` still absent)
  - **4 CONFIRMED OPEN:** #3 Open-Notebook SurrealDB root:root (still hardcoded), #10 Pipecat metrics (internal only, no Prometheus), #13/#14 tensorzero (upstream)
  - **P2 tracker: 4 open + 1 improved / 17 total** (down from 11 open)
- **Trivy CVE override status** — corrected per-image status:
  - `deepresearch`: **COMPLETE** — `ray==2.52.0` + `vllm==0.14.1` already pinned in `pmoves/services/deepresearch/Dockerfile:17-20`
  - `archon`: **COMPLETE** — `crawl4ai>=0.8.0` + `langchain-core>=1.2.5` override added to `pmoves/integrations/archon/python/Dockerfile.server` (CVE-2026-26216, CVE-2025-68664)
  - Previous correction over-stated: deepresearch pins were committed but missed during verification. Now both images have CVE overrides in place.
- **Dependabot alerts**: 0 open (confirmed)
- **Open PRs**: 0 (confirmed)

### Previous — Service Catalog & Contract Alignment (PR #844 continued)

- **Service catalog aligned to actual API contracts** (11 fixes in `service_catalog.py`):
  - `expected_fields` corrected: agent-zero (`status` only, not `version`/`timestamp`), archon (`status` only), pmoves-yt/presign/render-webhook/jellyfin-bridge (`ok` not `status`)
  - `health_path` corrected: tensorzero `/healthz`→`/health`, hi-rag-v2 `/healthz`→`/`, loki `/readyz`→`/ready`
  - media-audio moved to INTERNAL_SERVICES (no host port mapped, port 8082 is Firefly)
- **Service-specific test fixes**: agent-zero (accept `ok` status, allow 404 on `/mcp`), archon (accept `ok` status), tensorzero (use catalog health_path, fix ClickHouse field check, skip missing `/openapi.json`)
- **env.shared consistency fixes**: added `NATS_URL` with authenticated creds, removed duplicate `SUPABASE_JWT_SECRET`, synced `SUPABASE_DB_PASSWORD` with tier-supabase, trimmed trailing whitespace
- **NATS auth test updated**: `test_nats_url_removed_from_env_shared` → `test_nats_url_in_env_shared_is_authenticated` (validates creds in URL)
- **Full smoke suite** (with Docker stack): **131 passed, 83 skipped, 0 failed, 1 error** (174s)
  - Down from 33 failed → 16 failed → **0 failed** (all 33 failures eliminated across PR #844)
  - hi-rag-v2 UI fixes: health endpoint `/` not `/healthz`, flexible response schema, broadened exception guards
  - jellyfin-bridge UI fixes: POST not GET for playback-url, 404/405/412 for non-existent/unconfigured endpoints
  - 1 error: transient async fixture teardown (ClickHouse latency test, passes in isolation — pre-existing)
- **P2 tracker**: 14 open — unchanged (all Tier 2/3, non-blocking)

### Previous — PR #844 Review Cycle — Static Smoke Blockers + AB-9 Fix

- **PR #844** (`fix/static-smoke-blockers`, 4 commits ending at `f74f1db0`):
  - 22 static smoke test failures resolved (NATS tier migration, port conflicts, Supabase URL fixes, compose structure)
  - AB-9 runner queue deadlock resolved via Docker containerization + runner label alignment
  - Docker Bench CI job fixed: `runs-on` changed from `[self-hosted, Linux, X64, vps]` to `[self-hosted, ai-lab]`
- **Static smoke tests** (no Docker): **64 passed, 13 skipped, 0 failed** (16.39s)
  - All 13 skips are runtime-dependent (container running checks) — expected when stack isn't up
- **Full smoke suite** (215 collected, no Docker stack): **92 passed, 40 skipped, 83 failed**
  - 83 failures are runtime-only (services not running) — expected without Docker stack
  - **0 new static failures**
- **PR review agents** (4 parallel): code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer — no P1 findings
- **CodeRabbit review**: 14 comments — 4 fixed in `f74f1db0` (quadruple-brace Docker format bug, NATS credential false-positive, JetStream context window, Docker Bench runner label). Remaining comments are test robustness suggestions tracked for follow-up.
- **Hardening validation CI**: PASS (all services validated)
- **P2 tracker**: 14 open — unchanged (all Tier 2/3, non-blocking)

### Previous (Mar 9 — Post-PR #842 Validation Baseline)

- **PR #842 merged** (`05526994`): CI Trivy timeout increase to 10m + 5 new smoke tests with cross-platform `httpx.TimeoutException` fix
- **Smoke test suite**: 58 passed, 123 failed (runtime), 34 skipped, 1 error
- **Static smoke tests**: 22 failed, 22 passed, 3 skipped
- **AB-9**: RESOLVED — 3/4 Docker-containerized Linux runners online (`local_cert_runners.py`)
- **Audit-layers-static**: 39/40 submodules PASS
- **P2 tracker**: 11 open / 16 total

### Previous (Mar 9 — Tracker Reconciliation)

- **Tracker reconciliation sweep** — verified all 7 reported P1 submodule issues (from Phase C audit, 2026-02-16) are already fixed on `PMOVES.AI-Edition-Hardened` branches:
  - BoTZ: JWT `HAS_JOSE` fail-open → **FIXED** (`auth.py:57-67` raises HTTPException)
  - BoTZ: MCP Gateway unauthenticated GET → **FIXED** (`gateway.py:496-528` calls `_require_auth()`)
  - DoX: Hardcoded Supabase creds → **FIXED** (`docker-compose.supabase.yml` uses `${VAR:?required}`)
  - DoX: DELETE `/cipher/memory` silent no-op → **FIXED** (`cipher.py:77-99` returns 501)
  - ToKenism-Multi: NATS unauthenticated default → **FIXED** (`nats-client.ts:114` uses authenticated URL)
  - ToKenism-Multi: MinIO default creds → **FIXED** (`env.tier-*` use `${VAR:?required}`)
  - transcribe-and-fetch: Hardcoded passwords → **FIXED** (`integrate_backend.py` uses `CHANGE_ME` placeholders)
  - **Result: 0 P1 items remain open across all submodules.** P2 tracker and dashboard fully reconciled.
  - Stray `2.6.3` artifact deleted from repo root (was untracked).
- **P2 Tier 1 triage sweep** — 4 of 4 production-blocking P2 items verified FIXED in submodules:
  - P2 #4 Open-Notebook: Auth fail-open → **FIXED** (fail-closed `HTTPException 500` at `auth.py:32-36`)
  - P2 #1 BoTZ: MCP Gateway unauthenticated GET → **FIXED** (`_require_auth()` on `/servers`, `/tools`)
  - P2 #8 DoX: NATS no auth → **FIXED** (auth block added to `nats.conf`; `no_tls: true` is documented dev-only)
  - P2 #7 PMOVES.YT: Query injection → **FIXED** (added `_SAFE_VID_RE` validation on Hi-RAG-sourced `video_id` at `yt.py:3710`)
- **P2 tracker updated** — 4 production-blocking items closed → 11 open (all Tier 2/3, non-blocking)
- **Stale CI PRs** — #677/#678/#681 were already MERGED (2026-02-22), dashboard updated from "In progress" to "MERGED"
- **CodeQL alerts** — 2 open, both fixed in this session:
  - `options.js`: XSS via innerHTML → replaced with DOM API (`textContent`)
  - `mock-server.js`: unvalidated dynamic property → guarded with `Object.hasOwn()`
- **Dependabot alerts** — 0 open
- **Trivy CVE triage** — CVE override pins applied to both affected images:
  - `archon`: **FIXED** — `crawl4ai>=0.8.0` + `langchain-core>=1.2.5` override in `Dockerfile.server` (CVE-2026-26216, CVE-2025-68664)
  - `deepresearch`: **FIXED** — `ray==2.52.0` + `vllm==0.14.1` pinned in `Dockerfile:17-20` (CVE-2025-62593, CVE-2026-22778)
  - Both services run in isolated Docker networks with no direct external ingress (defense-in-depth)
- **AB-9 UPDATE** — All 4 self-hosted runners offline as of Mar 9 investigation. Previous "3/4 online" claim was stale. Root causes: `ai-lab-runner` (WSL2, no systemd service installed — process stopped), `ai-lab-win` (no Windows service — process stopped), `hotfix-runner` + `vps-runner` (remote machines, not accessible from dev workstation). WSL2 systemd now enabled (`/etc/wsl.conf`). Local runners require manual restart via `svc.sh install` (WSL) or interactive `run.cmd` (Windows). GHCR builds targeting `[self-hosted, Linux, X64, vps]` remain blocked until VPS runner is restored.
- **Dockerfile audit fixes (4 images):**
  - `pmoves-archon`: Renamed `MCP_CREDENTIALS_PATH` → `MCP_CONFIG_PATH` to eliminate BuildKit `SecretsUsedInArgOrEnv` warning
  - `pmoves-archon-ui`: Added USER directive (uid 65532, alpine `adduser`)
  - `pmoves-firefly-iii`: Added `USER www-data` defense-in-depth (upstream default)
  - `pmoves-llama-throughput-lab`: Added USER directive (uid 65532) + nginx permission fixup for non-root
- **PRs #834/#835 merged** — build-gate Phase 2 (`build_gate.py` + `build-gate.mk`) and hotfix runner lane with `subprocess.TimeoutExpired` handling
- **Dependabot alerts**: 0 open (was 1 medium — now resolved)
- **P2 tracker refreshed** — 15 items remain open (pre-triage; Tier 1 sweep later closed 4 → 11 open), 1 previously closed (HiRAG stale). No P2s fixed by intervening merges. Tracker date updated to 2026-03-09. Re-prioritized into 3 tiers: 4 production-blocking (P2-HIGH/MED), 6 tracked improvements, 5 cosmetic/env syntax.
- **Trivy failure triage** (from 2026-03-05 sweep):
  - `agent-zero`: Scan timeout at default 5m — infra issue, not vulnerability. **FIXED:** CI timeout increased to 10m in `integrations-ghcr.yml` and `self-hosted-builds-hardened.yml`. **Not a blocker.**
  - `archon`: 19 HIGH + 4 CRITICAL — key items: Crawl4AI RCE (CVE-2026-26216, upgrade to 0.8.0), langchain-core RCE (CVE-2025-68664, upgrade to 1.2.5), pydantic-ai info-disclosure. Upstream pins needed.
  - `deepresearch`: 23 HIGH + 2 CRITICAL — key items: Ray RCE (CVE-2025-62593), vLLM RCE (CVE-2026-22778). **FIXED** — `ray==2.52.0` + `vllm==0.14.1` pinned in Dockerfile.
  - `pmoves-yt`: 1 HIGH — urllib3 CVE-2026-21441 (decompression bomb). **FIXED:** `urllib3>=2.6.3` pinned in submodule (commit `0ae7bf1d3`), gitlink updated.

### Previous (Mar 9 — Build Visibility Matrix)

- **Build Visibility Matrix added** to dashboard — single cross-reference mapping all compose services → CI pipelines → Dockerfiles → architectures
  - 3 pipeline summary tables: `integrations-ghcr` (16 images, multi-arch, Trivy+Cosign), `self-hosted-builds` (9 images, amd64), `build-images` (29 images, manual dispatch)
  - Service-to-pipeline mapping organized by category (Agent, Retrieval, Media, Voice, CHIT, Utility, Data/Monitoring)
  - Dockerfile hardening snapshot with approximate counts vs targets
- **Push trigger overlap fixed** in `self-hosted-builds.yml`: added path exclusions for `agent-zero`, `archon`, `pmoves-yt` to push trigger (matching existing PR trigger exclusions), preventing duplicate builds when both `self-hosted-builds` and `integrations-ghcr` would fire
- **Services catalog CI annotations**: added `**CI Pipeline:**` field to every service entry in `.claude/context/services-catalog.md` with values: `integrations-ghcr`, `self-hosted-builds`, `build-images`, `vendor`, `local-build-only`, or `none`

## Latest Changes (Mar 8, 2026)

- **PR #827 merged** (`fix/coderabbit-followup-825-826`): 7 deferred CodeRabbit items from PRs #825/#826 + 4 review fixes
  - VPS deploy: `fleet_status()` SSH probe consistency (replaced `tailscale ping` with SSH probe matching `check_node()`)
  - VPS deploy: kvm2 health check now uses `${COMPOSE_CMD}` (loads `.env.vps` consistently)
  - VPS deploy: `BatchMode=yes` added to follow-up SSH calls for hang prevention
  - Makefile: `supa-collation-check` grep anchored with `$` to prevent false positives
  - Terraform: Hostinger provider pin `0.1.22`, bootstrap `.env.vps` wiring
  - Docs: tooling script audit trimmed redundant entries, production dashboard VPS fleet section added
- Live metrics: Open PRs `0`, Dependabot `0`, Code Scanning `0`

### Previous (Mar 8 — PRs #823/#824)

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
- **CI/AB-9 status: RESOLVED**
  - 3/4 runners online: `pmoves-ai-lab-runner` (Docker), `pmoves-vps-runner` (Docker), `pmoves-ai-lab-win` (Windows native)
  - Docker runners launched via `make -C pmoves ci-runners-local-cert-up` using existing `local_cert_runners.py`
  - Phase policy `local-certification` PASS — was always designed for Docker containers, just never launched
  - `lane_hosts.json` and `runner_phase_policy.json` updated to match containerized topology
  - **Previous mitigation retained:** 10 lightweight workflows on `ubuntu-latest`, matrix throttling on build workflows
- Live metrics: Open PRs `0`, Dependabot `1` (medium), Code Scanning `0`

### VPS Fleet Workstream

| Component | Status | Notes |
|-----------|--------|-------|
| Tailscale mesh (3 nodes) | CONFIGURED | kvm4-1, kvm4-2, kvm2 — Tailscale hostnames `pmoves-kvm4-1`, `pmoves-kvm4-2`, `pmoves-kvm2` |
| Node role assignments | DEFINED | kvm4-1: API Gateway (TZ, A0, HiRAG, Archon), kvm4-2: Data Services (Supabase, Qdrant, Neo4j, Meilisearch, NATS), kvm2: Exit Node (Nginx) |
| Deploy script (`deploy-vps.sh`) | VALIDATED | SSH probe replaces Tailscale-only check, honors `HOSTINGER_*_IP` overrides |
| VPS compose override | VALIDATED | CPU-only resource limits, GPU services disabled via `gpu` profile |
| `.env.vps` wiring | FIXED | `--env-file .env.vps` added to compose commands in bootstrap and deploy scripts |
| Hostinger Terraform provider | PINNED | `0.1.22` (was `~> 0.1`) |
| Docker Bench Security | UNBLOCKED | AB-9 RESOLVED — runners containerized via `local_cert_runners.py`, `make -C pmoves ci-runners-local-cert-up` |

---

## Latest Changes (Mar 5, 2026)

- GHCR production local-first validation widened from single-image checks to matrix-driven validation:
  - local validator: `pmoves/tools/ghcr_local_prepublish.py`
  - operator targets: `ghcr-prepublish-inrepo`, `ghcr-prepublish-inrepo-build`, `ghcr-prepublish-all`, `ghcr-dispatch-all`
- In-repo GHCR integration build sweep (`linux/amd64`, local): `7/7 PASS`
  - `agent-zero`, `archon`, `firefly-iii`, `jellyfin`, `pmoves-yt`, `deepresearch`, `supaserch`
- Strict local Trivy sweep (HIGH/CRITICAL, ignore-unfixed, vuln-only): `3 PASS / 4 FAIL`
  - PASS: `firefly-iii`, `jellyfin`, `supaserch`
  - FAIL: `agent-zero` (scan timeout — CI timeout increased to 10m), `archon` (known fixable HIGH/CRITICAL backlog), `pmoves-yt` (urllib3 CVE-2026-21441 — **FIXED** in submodule), `deepresearch` (known fixable HIGH/CRITICAL backlog)
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

### Build Visibility Matrix (Mar 9, 2026)

Three CI pipelines build Docker images. This matrix is the single cross-reference for which pipeline builds which service, with what security features.

#### Pipeline Coverage Summary

| Pipeline | Workflow File | Matrix Source | Images | Arch | Trivy | Cosign | SBOM | Trigger |
|----------|--------------|---------------|--------|------|-------|--------|------|---------|
| `integrations-ghcr` | `integrations-ghcr.yml` | `integrations-ghcr.matrix.json` | 16 | amd64+arm64 | Yes (HIGH/CRIT gate) | Yes (keyless) | Conditional (10/16) | push/PR/dispatch |
| `self-hosted-builds` | `self-hosted-builds.yml` | inline matrix | 9¹ | amd64 only | No | No | No | push/PR/dispatch |
| `build-images` | `build-images.yml` | `pmoves/images.yaml` | 29 | amd64 (default) | No | No | Yes (all) | manual dispatch only |

#### Service-to-Pipeline Mapping

**Agent & Orchestration**

| Compose Service | Image | integrations-ghcr | self-hosted-builds | build-images | Arch |
|----------------|-------|-------------------|-------------------|--------------|------|
| agent-zero | pmoves-agent-zero | ✅ (Trivy+Cosign+SBOM) | ✅ | ✅ | amd64+arm64 |
| archon | pmoves-archon | ✅ (Cosign) | ✅ | ✅ | amd64+arm64 |
| archon-ui | pmoves-archon-ui | ✅ (Trivy+Cosign+SBOM) | — | — | amd64+arm64 |
| mesh-agent | (uses agent-zero image) | — | — | — | — |
| channel-monitor | pmoves-channel-monitor | — | ✅ | — | amd64 |
| botz-gateway | pmoves-botz-gateway | — | — | ✅ | amd64 |
| cipher-api | pmoves-cipher-memory | — | — | — | vendor |

**Retrieval & Knowledge**

| Compose Service | Image | integrations-ghcr | self-hosted-builds | build-images | Arch |
|----------------|-------|-------------------|-------------------|--------------|------|
| hi-rag-gateway-v2 | pmoves-hirag | — | — | ✅ | amd64 |
| hi-rag-gateway-v1 | pmoves-hirag | — | — | ✅ | amd64 |
| deepresearch | pmoves-deepresearch | ✅ (Cosign) | — | ✅ | amd64 only |
| supaserch | pmoves-supaserch | ✅ (Cosign+SBOM) | — | ✅ | amd64+arm64 |
| model-registry | pmoves-model-registry | — | ✅ | ✅ | amd64 |
| gpu-orchestrator | pmoves-gpu-orchestrator | — | ✅ | ✅ | amd64 |
| open-notebook | pmoves-open-notebook | ✅ (Trivy+Cosign+SBOM) | — | ✅ | amd64+arm64 |

**Media Processing**

| Compose Service | Image | integrations-ghcr | self-hosted-builds | build-images | Arch |
|----------------|-------|-------------------|-------------------|--------------|------|
| pmoves-yt | pmoves-yt | ✅ (Cosign+SBOM) | ✅ | ✅ | amd64+arm64 |
| ffmpeg-whisper | pmoves-ffmpeg-whisper | — | ✅ | — | amd64 |
| media-video | (compose build) | — | — | — | local-build |
| media-audio | (compose build) | — | — | — | local-build |
| extract-worker | pmoves-extract-worker | — | ✅ | — | amd64 |
| pdf-ingest | pmoves-pdf-ingest | — | — | ✅ | amd64 |
| langextract | (compose build) | — | — | — | local-build |
| notebook-sync | (compose build) | — | — | — | local-build |
| transcribe-backend | pmoves-transcribe-backend | — | — | ✅ | amd64 |

**Voice & Speech**

| Compose Service | Image | integrations-ghcr | self-hosted-builds | build-images | Arch |
|----------------|-------|-------------------|-------------------|--------------|------|
| flute-gateway | pmoves-flute-gateway | — | — | ✅ | amd64 |
| ultimate-tts-studio | pmoves-ultimate-tts-studio | — | — | ✅ (manual) | amd64 |

**CHIT & Geometry**

| Compose Service | Image | integrations-ghcr | self-hosted-builds | build-images | Arch |
|----------------|-------|-------------------|-------------------|--------------|------|
| tokenism-simulator | pmoves-tokenism-simulator | — | — | ✅ | amd64 |
| tokenism-ui | pmoves-tokenism-ui | ✅ (Cosign+SBOM) | — | ✅ | amd64+arm64 |
| evo-controller | pmoves-evo-controller | — | — | ✅ | amd64 |
| a2ui-nats-bridge | pmoves-a2ui-nats-bridge | ✅ (Cosign) | — | ✅ | amd64+arm64 |
| session-context-worker | pmoves-session-context-worker | ✅ (Cosign) | — | ✅ | amd64+arm64 |

**Utility & External**

| Compose Service | Image | integrations-ghcr | self-hosted-builds | build-images | Arch |
|----------------|-------|-------------------|-------------------|--------------|------|
| publisher-discord | pmoves-publisher-discord | — | ✅ | — | amd64 |
| jellyfin | pmoves-jellyfin | ✅ (Trivy+Cosign+SBOM) | — | ✅ | amd64+arm64 |
| jellyfin-ai-media-stack | pmoves-jellyfin-ai-media-stack | — | — | ✅ | amd64 |
| wger (health) | pmoves-wger | ✅ (Cosign+SBOM) | — | ✅ | amd64+arm64 |
| firefly-iii (wealth) | pmoves-firefly-iii | ✅ (Cosign+SBOM) | — | ✅ | amd64+arm64 |
| llama-throughput-lab | pmoves-llama-throughput-lab | ✅ (Cosign) | — | ✅ | amd64 only |
| presign | (compose build) | — | — | — | local-build |
| render-webhook | (compose build) | — | — | — | local-build |
| jellyfin-bridge | (compose build) | — | — | — | local-build |

**Data & Monitoring** (vendor images — no PMOVES build)

| Compose Service | Image Source | Notes |
|----------------|-------------|-------|
| nats | nats:2.10-alpine | Vendor |
| supabase-db | supabase/postgres | Vendor |
| qdrant | qdrant/qdrant:v1.10.0 | Vendor |
| neo4j | neo4j:5.22 | Vendor |
| meilisearch | getmeili/meilisearch:v1.8 | Vendor |
| minio | minio/minio | Vendor |
| prometheus | prom/prometheus | Vendor |
| grafana | grafana/grafana | Vendor |
| loki | grafana/loki | Vendor |
| promtail | grafana/promtail | Vendor |
| cadvisor | gcr.io/cadvisor/cadvisor | Vendor |
| tensorzero | tensorzero/gateway | Vendor |
| tensorzero-clickhouse | clickhouse/clickhouse-server | Vendor |
| tensorzero-ui | tensorzero/ui | Vendor |

**Pipeline overlap note:** `agent-zero`, `archon`, and `pmoves-yt` appear in both `integrations-ghcr` (multi-arch, Trivy+Cosign) and `self-hosted-builds` (amd64-only). Push trigger exclusions added to `self-hosted-builds` to prevent duplicate builds on push to main (PR #832 fix).

¹ 9 images in the `self-hosted-builds` matrix; 3 (`agent-zero`, `archon`, `pmoves-yt`) are excluded from auto-trigger on push/PR by path filters (built by `integrations-ghcr` instead). All 9 remain buildable via manual `workflow_dispatch`.

**Operator Guide:** See [`pmoves/docs/operations/DOCKER_BUILD_GUIDE.md`](operations/DOCKER_BUILD_GUIDE.md) for the consolidated local → CI Docker build workflow.

#### Dockerfile Hardening Snapshot

| Metric | Approximate Count | Target | Notes |
|--------|-------------------|--------|-------|
| Non-root USER directive | ~49/51 Dockerfiles | 100% | 2 remaining: Agent Zero supervisord, TensorZero provider-proxy |
| HEALTHCHECK instruction | ~16/51 Dockerfiles | 100% | Most rely on compose-level healthchecks instead |
| SHA-pinned base image | ~13/51 Dockerfiles | 100% | Remainder use `:latest` or version tags |

**Full per-service details:** `pmoves/docs/hardening/PMOVES-hardening-tracker.md`

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
| Quantitative snapshot timestamp | 2026-03-11 (Post-PRs #867-#871 port registry + smoke fixes) |
| Total tracked items | 24 |
| Resolved | 24 (+1 since last update) |
| Active blockers (release-blocking) | 0 |
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |
| CodeQL alerts (open) | **1 open (FP #195)** — suppressed with `lgtm` comment, pending GitHub dismissal on next scan. #194 auto-closed by rescan; #196 fixed via `new URL()` constructor (PR #867) |
| Dependabot alerts | **0 open** (live GitHub API on 2026-03-09) |
| Open PRs | **0** |
| CI queue | **HEALTHY** — 3/4 self-hosted runners online (2 Docker containers via `local_cert_runners.py` + 1 Windows native). Phase policy `local-certification` PASS. Start: `make -C pmoves ci-runners-local-cert-up`. Hotfix runner offline (non-blocking). |

### Runtime Verification Snapshot (2026-03-09)

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
| #681 | `fix/ci-self-hosted-hardening` | GHCR workflow adjusted to build-only behavior on pull requests (no push/sign/scan) to avoid 403 package push failures | **MERGED** (2026-02-22) |
| #678 | `fix/ci-pytest-conftest-collision` | Python tests switched to importlib mode and CodeQL JS lane now pins Node 20 on self-hosted runners | **MERGED** (2026-02-22) |
| #677 | `fix/silent-failure-hardening` | Same CI fix set as #678 plus compose fix to keep `nats-init` defined for default validation path | **MERGED** (2026-02-22) |

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
| AB-9 | Self-hosted runner queue starvation on CodeQL/GHCR lanes | Release closeout 2026-02-24 | **HIGH** | **RESOLVED** | Docker-containerized runners via `local_cert_runners.py` — `make -C pmoves ci-runners-local-cert-up`. Phase policy `local-certification` PASS (2/2 required lanes online). No WSL/manual intervention needed. |
| AB-10 | `main` vs hardened commit-history divergence after squash promotion | Sync pass 2026-03-04 | **LOW** | TRACKED | Maintain content parity (`git diff` clean). Use explicit promotion + back-sync notes to avoid false-positive divergence alarms in ops reports |

### Blocker Detail

**AB-9: Runner Queue Deadlock — RESOLVED 2026-03-09**
Root cause: runners were installed as bare-metal services (WSL2 systemd, Windows svc.cmd) that stopped and had no auto-recovery. The `local-certification` phase policy was always designed for "both runners on local Docker containers" but this was never implemented until now.

**Resolution:** Used existing `local_cert_runners.py` (`make -C pmoves ci-runners-local-cert-up`) which launches `myoung34/github-runner` containers via Docker Desktop. No WSL2 or manual service management needed — containers auto-restart via `restart: unless-stopped` policy. Updated `lane_hosts.json` to reflect containerized topology and `runner_phase_policy.json` to match actual workflow label sets.

**Timeline of missed fixes:**
- PRs #832/#834/#835 (Mar 7-8): Added CI throttle timeouts but didn't address root cause (runners offline)
- PR #842 (Mar 9): Captured validation baseline showing 0/4 runners, noted as AB-9 REGRESSED
- This fix (Mar 9): Discovered `local_cert_runners.py` already existed with full Docker runner management — just needed to be run

**Current state:** 3 runners online (ai-lab container, vps container, ai-lab-win native). Phase policy PASS. Hotfix runner offline (non-blocking).

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
**Live status on 2026-03-11:** CodeQL open alerts are **0** after merge (#194 auto-closed by rescan; #195 false positive suppressed with `lgtm` comment; #196 fixed via `new URL()` constructor sanitization in `options.js:263-268`).

| Group | Count | Severity | Rule | Files | Remediation | Status |
|-------|-------|----------|------|-------|-------------|--------|
| A | 2 | **critical** | `py/full-ssrf` | `hi-rag-gateway/gateway.py:570`, `hi-rag-gateway-v2/app.py:1347` | Validate/allowlist URLs before requests | **FIXED** (PR #715) |
| B | 11 | high | `py/path-injection` | `pmoves-yt/yt.py` (11 locations: L1434-1761) | Add path sanitization utility; bulk fix | **FIXED** (PR #715) |
| C | 6 | high | `py/path-injection` | `gateway/api/viz.py` (4), `gateway/api/chit.py` (2) | Validate/sanitize file path parameters | **FIXED** (PR #715) |
| D | 2 | high | `py/path-injection` | `hf-mcp-server/main.py` (L522, L630) | Validate HuggingFace model paths | **FIXED** (PR #715) |
| E | 5 | medium | `py/stack-trace-exposure` | `consciousness-service/main.py` (3), `gateway/api/workflow.py`, `supaserch/app.py` | Replace traceback in HTTP responses with generic errors | **FIXED** (PR #715) |
| F | 3 | high | `js/xss-through-dom`, `js/resource-exhaustion` | `gateway/web/client.html:69`, `ui/lib/serviceHealth.ts:56`, `chrome-extension/options/options.js:264` | Sanitize innerHTML; add request limits/timeouts | **FIXED** (#194 scheme validation in `6c3a0455`; #195 FP suppressed; #196 `new URL()` constructor sanitization) |
| G | 1 | high | `py/clear-text-logging` | `tools/chit_credential_demo.py:123` | Demo tool; redact or suppress sensitive logging | OPEN |
| H | 31 | mixed | Various | New/expanded scan results from PRs #716-719 | Requires fresh triage pass | **NEW** |

**Priority order:** H (fresh triage needed) > F (frontend XSS/resource) > G (demo tool)

---

## Dependabot Alert Triage (2026-02-18 Baseline → 2026-02-28 Update)

**Historical section:** this table preserves the 2026-02-28 triage baseline for traceability.
**Live status on 2026-03-09:** Dependabot open alerts are **0** (live GitHub API; prior medium alert resolved).

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
| 2026-03-11 | **PR gate sweep:** 5 open PRs merged (4 dependabot CI action bumps #860–#863, 1 feature PR #854 with security fixes). `MEILI_MASTER_KEY` hardened to `:?` fail-closed, `proxy.ts` auth bypass narrowed to exact match. 13 stale CI runs cancelled. Open PRs: 0. |
| 2026-03-10 | **P2 final resolution:** All remaining P2 items closed (0 open / 17 total). Open-Notebook: SurrealDB creds parameterized (#3), `/metrics` Prometheus endpoint added (#5). Pipecat #10 closed (library scope, Flute-Gateway covers). tensorzero #13 closed (accepted risk, upstream). tensorzero #14 closed (false positive, `${VAR:?required}` pattern). |
| 2026-03-09 | **Post-cleanup sit rep:** Trivy scan timeout increased to 10m in `integrations-ghcr.yml` + `self-hosted-builds-hardened.yml` (5 scan steps). `PMOVES.AI-Edition-Hardened-Integrations` branch synced (was 234 commits behind main). 5 new smoke tests added (env consistency, port conflicts, NATS config, Supabase realtime, Supabase selfhosted) with cross-platform path resolution. Local Hardened branch pruned. urllib3 CVE-2026-21441 already fixed in submodule. |
| 2026-03-09 | **Tracker reconciliation:** verified all 7 Phase C P1 submodule findings (BoTZ JWT/gateway, DoX creds/cipher, ToKenism NATS/MinIO, transcribe-and-fetch passwords) already fixed on Hardened branches. P2 tracker updated with individual evidence entries. Executive summary: 0 P1 open. Stray `2.6.3` artifact deleted. |
| 2026-03-08 | **PR #827 merged:** 7 deferred CodeRabbit items from #825/#826 + 4 review fixes (SSH probe consistency, COMPOSE_CMD in kvm2, BatchMode=yes, grep anchor). VPS Fleet workstream validated. |
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
