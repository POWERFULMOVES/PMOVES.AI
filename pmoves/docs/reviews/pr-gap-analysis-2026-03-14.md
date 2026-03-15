# PR Gap Analysis — PMOVES Ecosystem Integration Review

**Date**: 2026-03-14
**Scope**: 12 open PRs reviewed against PMOVES ecosystem integration checklist
**Reviewers**: 9 parallel analysis agents

---

## Executive Summary

| PR | Verdict | Blocking Issues | Key Gaps |
|----|---------|-----------------|----------|
| #905 | **FIX REQUIRED** | P1 hardcoded passwords, port 8096 conflict | Missing network, TensorZero bypass, non-Prometheus metrics |
| #906 | **CLOSE (duplicate of #922)** | 59-file overlap with #922 | Unauthenticated routes, SSRF, scope creep |
| #914 | **CLOSE (superset is #915)** | Stale branch, all UI fixes already on main | agent_hint removal needs rationale |
| #915 | **REBASE + STRIP** | .gitmodules conflict, 7 unrelated changes bundled | Only 2 compose healthcheck fixes are real |
| #916 | **SPLIT REQUIRED** | 4 unauthenticated API routes, SSRF | Overlaps #922 on routes; docs are unique value |
| #922 | **FIX REQUIRED (superset)** | No auth, orphaned nav pages, dead code | Best candidate for UI merge after fixes |
| #924 | **CLOSE (superseded)** | 100% already on main | Dual-submodule antipattern |
| #925 | **CLOSE or cherry-pick** | 111/114 files already merged | Only 3 real files remain |
| #926 | **FIX REQUIRED** | P0 Dockerfile broken, auth fail-open, syntax error | Good architecture, needs build fixes |
| #927 | **FIX REQUIRED** | NATS auth stripped, nonexistent subjects | Hard dependency on #926 |
| #928 | **FIX REQUIRED** | CRITICAL secret logging, no webhook HMAC | Non-functional NATS path |
| #929 | **FIX REQUIRED** | Only 5/9 CodeQL alerts fixed, 3 new introduced | Allowlist key mismatch bug |

### Recommended Merge Order

1. **#929** (CodeQL fixes) — after fixing remaining 4 alerts
2. **#915** (healthcheck fixes) — after stripping to compose-only changes
3. **#905** (CONCH Pipeline) — after security fixes
4. **#922** (UI superset) — after auth + nav fixes
5. **#926** (Cast TTS) — after Dockerfile + auth fixes
6. **#927** (Pipecat Cast) — after #926 merged
7. **#928** (GitHub Webhook) — after secret logging + HMAC fixes
8. **Close**: #906, #914, #924, #925
9. **Split**: #916 (docs only PR + close API route portions)

### Cross-PR Conflict Map

```
#906 ←——59 files——→ #922   (CLOSE #906, keep #922)
#916 ←——14 files——→ #922   (Split #916, keep #922 routes)
#906 ←——12 files——→ #916   (Transitively resolved by closing #906)
#914 ⊂ #915                 (CLOSE #914, keep #915)
#926 ←—depends—→ #927      (Merge #926 first)
#905 ←—3 lines—→ #929      (Merge #929 first, rebase #905)
```

---

## PR #905 — CONCH Pipeline (CHR Algorithm & CGP Generation)

### Missing Integrations

- **Port 8096 conflict with Cipher Memory**: `consciousness-service` uses `${CONSCIOUSNESS_HOST_PORT:-8096}:8096` but Cipher Memory already occupies port 8096 (`${CIPHER_PORT:-8096}:3000`). Must assign a different port.
- **Missing `pmoves_bus` network**: The service only joins `pmoves_app` but publishes to NATS. Without `pmoves_bus`, NATS at `nats:4222` is unreachable. Every other NATS-publishing service includes `pmoves_bus`.
- **Embeddings bypass TensorZero**: `chr_algorithm.py` loads `SentenceTransformer("all-MiniLM-L6-v2")` locally instead of routing through TensorZero gateway (`POST http://tensorzero:3000/v1/embeddings`). Misses centralized observability.
- **No `env.shared.example` update**: `CONSCIOUSNESS_HOST_PORT` and `CONSCIOUSNESS_IMAGE` not added to env templates.
- **CGP spec version mismatch**: Uses `"spec": "chit.cgp.v0.1"` — canonical naming is `chit.cgp.v1.0`.

### Security Gaps

- **P1: Hardcoded Postgres password** in `load_supabase_chunks.py` lines 1377/1393: `PGPASSWORD=zode0dl7/JgAaNoVqjzHQ0S5Iq1vi7Tt`. Must replace with `${DB_PASSWORD}`.
- **P1: Hardcoded Neo4j password** in `load_neo4j_consciousness.sh` line 1149: `NEO4J_PASSWORD="${NEO4J_PASSWORD:-pm_kDhuaogcUc1oOOVeGMNCkQ}"`. Must use `:?` fail-hard.
- **P2: Hardcoded CHIT passphrase in Dockerfile**: `ENV CHIT_PROD_PASSPHRASE=pmoves-chit-default` provides deterministic bypass even though compose uses `:?` fail-hard.
- **P2: Exception details leaked** in 3 `HTTPException(detail=f"...{str(e)}")` patterns — same issue this PR fixes in `github-crossrepo-pr/app.py`.
- **P2: No RLS policies** on new `consciousness_theories` Supabase table.

### Observability Gaps

- **`/metrics` returns JSON, not Prometheus format**: Prometheus requires text exposition format. Use `prometheus_client` library.
- **No Prometheus scrape target**: `prometheus.yml` has no entry for consciousness-service.
- **Thread-unsafe metrics**: Module-level `int` globals instead of `prometheus_client.Counter`.

### Docker/Compose Issues

- **Healthcheck uses Python httpx import** — slow and fragile. Prefer `curl -sf`.
- **Missing `depends_on` for Supabase**: The `/chr/from-supabase` endpoint fetches from Supabase but only `nats-init` is in `depends_on`.
- **`start_period: 10s` too short** for model loading on cold start. Other ML services use 30-60s.
- **3 duplicate schema definitions** across `data/`, `db/`, and `supabase/initdb/` with conflicting schema names (`public` vs `pmoves_core`).

### Cross-PR Conflicts

- Shares `docker-compose.yml` with #915 — merge order matters.
- Shares `github-crossrepo-pr/app.py` with #929 (3 hunks) — merge #929 first.
- Submodule bumps (Archon, BoTZ) may conflict with #925, #927, #928.

---

## PR #906 — Mega UI Health Check (411 files)

### Verdict: CLOSE — Duplicate of #922

PR #906 and #922 share **59 identical files**. After rebase, #906's unique delta is ~44 files of which #922 is a strict superset (adds 3 dashboard pages, DashboardNavigation, type definitions on top of everything #906 has). Merging both would cause merge conflicts on every shared file.

### Security Gaps (also present in #922)

- **CRITICAL: All new API routes unauthenticated** — `/api/agents/taxonomy`, `/api/github/prs`, `/api/graphiti/trails`, `/api/services/health`, `/api/services-hub`, `/api/health-all` have zero JWT validation.
- **SSRF via `/api/services/health`**: Calls `checkAllServices()` 12 times per request (once per category + once each for all/critical). No auth + no rate limiting = SSRF amplifier.
- **`services-hub` still uses `edge` runtime** despite the PR description saying it was switched to `nodejs` for localhost DNS resolution.
- **X-Forwarded-For spoofing** in rate limiter — no proxy trust validation.

### Scope Alignment

PR title "fix: UI health check runtime fixes and rate limiting" but actually adds 3 new API routes, GEOMETRY BUS docs, TAC tree config, and Agent Zero plugins submodule. Should be split.

---

## PR #914 — TAC Tree (Agent Zero Customization)

### Verdict: CLOSE — #915 is a superset

PR #915 contains all 9 files from #914 plus docker-compose healthcheck fixes. After rebase, 3 of #914's 9 files (boot-jwt, playwright, with-env) will be no-ops (already on main).

### Key Finding

- **`agent_hint` removal**: v1.2.0 strips `agent_hint: codex` from all 59 leaf nodes. The TAC runner at `pmoves/tools/tac_runner.py:123` reads this field per-node. Removal needs documented rationale.
- **Merge conflict guaranteed**: Main has v1.1.0 (569 lines) from merged #907. This PR replaces with v1.2.0 (510 lines). Cannot merge without rebase.

---

## PR #915 — Healthcheck Fixes (flute-gateway, bgutil-pot-provider)

### Verdict: REBASE + STRIP to compose-only changes

Only `pmoves/docker-compose.yml` contains the actual healthcheck fixes. The other 8 files are unrelated bundled changes.

### Healthcheck Fixes (CORRECT)

- **flute-gateway**: `timeout=5→10`, Docker `timeout: 10s→15s`, `start_period: 15s→60s`. Correct for GPU-dependent TTS service.
- **bgutil-pot-provider**: `pgrep -f 'node|python'` → `kill -0 1`. Correct — `pgrep` binary absent from minimal image.

### Issues

- **`.gitmodules` conflict**: Main already has `PMOVES-a0-plugins` registered (from merged #907). PR adds it again at different position.
- **Scope creep**: 7 unrelated changes bundled (TAC tree, JWT fix, Playwright port, spawn handler, submodule adds, docs update). Strip to compose diff only.

---

## PR #916 — GEOMETRY BUS Documentation + pmovesui APIs

### Verdict: SPLIT — Docs are unique value, API routes duplicate #922

### Unique Value (KEEP — docs-only PR)

- `pmoves/docs/geometry-bus/` — comprehensive GEOMETRY BUS documentation (README, NATS taxonomy, integration guide, Mermaid diagrams)
- `pmoves/configs/tac_trees/` — TAC tree config
- `.gitignore`, `.gitmodules` updates

### Duplicate (CLOSE — overlaps #922)

- 4 API routes (`agents/taxonomy`, `github/prs`, `graphiti/trails`, `services/health`) — #922 has different implementations of the same routes.

### Security Gaps (shared with #922)

- **CRITICAL: No auth on any API route**
- **SSRF via `repo` query parameter** in GitHub PRs route — passes directly to GitHub API URL. Must validate against `PMOVES_REPOS` allowlist.
- **Error responses leak internal details** — `error.message` returned to clients.
- **Custom YAML parser is fragile** — hand-rolled 40-line regex parser. Use `js-yaml`.

### CHIT/GEOMETRY Issues

- **CGP spec version mismatch**: Existing context uses `v0.1`/`v0.2`, new docs use `v1.0`. Need to update canonical context files.
- **Port 8096 conflict documented but not resolved** between consciousness-service and cipher-memory.
- **Dead documentation links**: 4 referenced files not created by the PR.
- **New NATS subjects undocumented** in canonical context: `geometry.cgp.calibration.v1`, `geometry.packet.encoded.v1`, `agentgym.train.completed.v1`.

---

## PR #922 — pmovesui API Routes and Dashboard Pages

### Verdict: FIX REQUIRED — Best UI PR candidate after fixes

This is the **superset** of #906 and the API route portions of #916. After fixes, this should be the single UI merge.

### Missing Integrations

- **Navigation sidebar missing entries**: `NavKey` type updated with `'agents' | 'github' | 'graphiti'` but `NAV_ITEMS` array has no corresponding entries. 3 new dashboard pages are unreachable from navigation.
- **No NATS integration**: Graphiti trails reads static JSON from disk — doesn't subscribe to `agent.graphiti.signed.v1` for live updates.
- **No auth headers on API clients**: `lib/api/agent-zero.ts`, `lib/api/archon.ts`, `lib/api/flute.ts` (2,044 lines combined) send requests without authentication. Agent Zero MCP may require `MCP_CLIENT_ID`/`MCP_CLIENT_SECRET`.
- **2,044 lines of dead code**: 4 API client libraries not imported by any route or page in this PR.

### Security Gaps

- **CRITICAL: Zero authentication** on all 4 new API routes.
- **SSRF via `repo` param** — user-controlled input into GitHub API URL.
- **Hardcoded `http://localhost:8091`** in `getGitHubToken()` — only route without env var fallback.
- **`_getCHITPassphrase()` never validates signatures** — `signatureValid` is always `true` when sig exists.
- **`edge` runtime on health-enhanced** contradicts PR's own fix to switch from edge to nodejs.

### Cross-PR Conflicts

- **59 shared files with #906** — close #906.
- **14 shared files with #916** (including 4 API routes with different implementations) — split #916.
- **`playwright.config.ts`** changed in all 3 UI PRs.

### Navigation/UX Issues

- 3 orphaned dashboard pages (no sidebar links)
- No loading states on agents dashboard
- No accessibility (skip links, ARIA live regions)
- Health endpoint now returns 503 on DB failure — potential cascading restart in Docker/K8s

### Missing Environment Variables (undocumented)

`NEXT_PUBLIC_AGENT_ZERO_URL`, `AGENT_ZERO_URL`, `NEXT_PUBLIC_ARCHON_URL`, `ARCHON_URL`, `NEXT_PUBLIC_FLUTE_GATEWAY_URL`, `FLUTE_GATEWAY_URL`, `NEXT_PUBLIC_FLUTE_WS_URL`, `FLUTE_WS_URL`, `SMOKE_SHARED_SECRET`, `PRESIGN_SERVICE_URL` — none in `env.shared.example`.

---

## PR #924 — Neo4j Submodule Integration

### Verdict: CLOSE — 100% superseded by main

All Neo4j Makefile targets already exist on main (merged via `d6e597da`). The PR introduces a **dual-submodule antipattern** — registering the same repo at `pmoves/integrations/neo4j` when it already exists at root-level `PMOVES-Neo4j`.

- Missing branch pin in `.gitmodules` (root submodule correctly pins to `PMOVES.AI-Edition-Hardened`)
- No credential handling (main's version reads `NEO4J_AUTH` from `env.tier-data`)
- No backup/restore targets (main already has them)
- Directly conflicts with #925 which tries to delete the same Neo4j targets

---

## PR #925 — Network Fabric + GitHub App + DEPLOYER

### Verdict: CLOSE or cherry-pick 3 files

PR body claims 114 files but **111/114 were already merged** in PRs #887-918. Actual unique diff:

1. `PMOVES-Tailscale` — gitlink bump (unverified)
2. `pmoves/docs/GITHUB_APP_IMPLEMENTATION_SUMMARY.md` — deletion of 0-byte file
3. `pmoves/scripts/deploy_to_5090.sh` — new 100-line script with hardcoded IP (`192.168.1.65`) and username (`Administrator`)

### Security Gaps

- Hardcoded private IP and Administrator username in deploy script — should be parameterized.
- Stale branch artifact: would delete comprehensive Neo4j Makefile targets from main if merged without rebase.

---

## PR #926 — Cast TTS Gateway

### Missing Integrations

- **Not in main `docker-compose.yml`** — standalone compose only. Other services can't discover it.
- **No profile assignment** — can't start with `docker compose --profile voice`.
- **No `depends_on`** for NATS, Flute-Gateway, or Ultimate-TTS.
- **NATS subjects don't align** with `skills.pipeline.voice-synthesis.v1` skill pairing. Uses entirely new namespace (`voice.cast.*`, `device.cast.*`).
- **Not in services-catalog** — port 8060 untracked.

### Security Gaps

- **P0: Dockerfile copies only 3 of 14 Python files** — container will crash with `ModuleNotFoundError`. Need `COPY *.py .`.
- **P0: Duplicate `record_check` method body** in `health.py` — syntax error.
- **P1: Auth fail-open** — `CAST_AUTH_REQUIRED` defaults to `"false"`, granting admin role with zero auth. Same BoTZ-style fail-open pattern.
- **P1: Path traversal** via `POST /cast/audio` — `audio_path` from request body passed directly to `catt cast` subprocess. No validation.
- **Missing `tmpfs` mounts** with `read_only: true` — Python needs `/tmp`.
- **Missing `security_opt: no-new-privileges`**.
- **Deprecated `version: '3.8'`** in compose.

### Observability

- `/healthz` and `/metrics` correctly defined. Prometheus metric names follow conventions.
- No Loki/Promtail labels configured.

---

## PR #927 — Pipecat Cast (Audio Processor + Voice-Follow Agent)

### Missing Integrations

- **NATS URL loses credentials**: `_resolve_nats_url()` defaults to `nats://127.0.0.1:4222` and strips `pmoves@` auth in Docker-to-host translation.
- **Subscribes to nonexistent NATS subjects**: `voice.agent.response.v1` and `agent.response.v1` — no PMOVES service publishes these.
- **No auth headers** when calling Cast TTS Gateway — will fail if #926's auth is enabled.
- **Duplicate `NotebookClient`** — both `cast_notebook_logger.py` and `voice_follow_cast_agent.py` implement identical Open Notebook clients.
- **No Dockerfile or compose entry** for voice-follow agent daemon.

### Cross-PR Dependencies

- **Hard dependency on PR #926** — makes HTTP calls to `http://localhost:8060/cast/speech`.
- Plugin follows existing a0-plugins pattern correctly. No plugin.yaml conflicts.

---

## PR #928 — GitHub Webhook Auto-Configuration

### Security Gaps

- **CRITICAL: Full secret logging** at line 1346: `print(f"\nGenerated secret: {webhook_secret}")`. Also at line 1203. CodeQL correctly blocking merge.
- **CRITICAL: No webhook HMAC signature verification** in n8n workflow. `x-hub-signature-256` header never checked. Arbitrary payloads accepted.
- **n8n webhook has no authentication** — `"authentication": "none"` on the configure endpoint.
- **NATS HTTP path non-functional**: Publishes to `http://nats:4222/pub` — NATS port 4222 is the client protocol, not HTTP. This silently fails.
- **`run_command()` uses `shell=True`** — code smell for security scanners.

### Missing Integrations

- **Missing files referenced in docs**: `github_webhook_processor_v2.json`, `secrets_manifest.yaml` changes, `docker-compose.n8n.yml` changes described in docs but not in diff.
- **NATS subjects not in catalog**: `github.webhook.configured.v1`, `github.webhook.failed.v1` undocumented.
- **Discord webhook placeholder URL** will produce HTTP errors in production.

---

## PR #929 — CodeQL Security Fixes

### Fix Correctness (5/9 resolved, 3 new alerts introduced)

| Alert | Rule | Fixed? | Still Flagged? |
|-------|------|--------|----------------|
| 209-211 | stack-trace-exposure (crossrepo-pr) | YES | NO |
| 206 | stack-trace-exposure (issue-triage) | YES | NO |
| 202 | url-substring-sanitization | PARTIAL | **YES** (line 151 `startswith` fallback) |
| 200 | clear-text-logging | PARTIAL | **YES** (taint still flows) |
| 201 | clear-text-logging (verify) | **BROKEN** | **YES** (allowlist key mismatch) |
| 199 | clear-text-logging (chit_sync) | YES | NO |
| 198 | clear-text-storage | PARTIAL | **YES** (`# nosec` is Bandit, not CodeQL) |

### Key Bugs

- **Allowlist key mismatch** in `verify_github_app_setup.py`: Allowlist has `{"gh_secrets", "env_tier", "secrets_funnel"}` but actual dict keys are `{"github_secrets", "env_tier_agent", "chit_manifest"}`. 3/6 checks silently swallowed as `"unknown_check"`.
- **`startswith("github.com")` fallback** re-introduces the substring check CodeQL flagged. `github.com.evil.com` passes.
- **`# nosec`** is Bandit-specific, not CodeQL. Has zero effect on CodeQL analysis.

### Cross-PR Conflicts

Shares 3 lines in `github-crossrepo-pr/app.py` with #905 — both replace `str(e)` with different generic strings. Merge #929 first.

---

## Cross-Cutting Findings

### 1. UI Auth Gap (affects #906, #916, #922)

**Every new API route across all 3 UI PRs lacks authentication.** This is a systematic gap — 7+ endpoints expose internal service topology, agent registry, GitHub data, and CHIT signatures to unauthenticated callers. A single auth middleware wrapping `/api/agents/*`, `/api/github/*`, `/api/graphiti/*`, `/api/services/*` would fix all three PRs.

### 2. Stale Branch Epidemic (affects #906, #914, #915, #924, #925)

5 of 12 PRs have stale branches where most content is already on main. This inflates file counts and creates false merge conflicts. All need rebase before merge.

### 3. NATS Subject Proliferation (affects #905, #916, #926, #927, #928)

5 PRs introduce new NATS subjects not in the canonical catalog:
- `voice.cast.*`, `device.cast.*` (#926)
- `voice.agent.response.v1`, `agent.response.v1` (#927)
- `github.webhook.*` (#928)
- `geometry.cgp.calibration.v1`, `geometry.packet.encoded.v1` (#916)
- Uses existing `geometry.cgp.v1`, `tokenism.cgp.ready.v1` correctly (#905)

All new subjects should be registered in `.claude/context/nats-subjects.md`.

### 4. Port 8096 Conflict (affects #905, #916)

Both consciousness-service and cipher-memory claim port 8096. One must change. Since cipher-memory is already in production compose, consciousness-service should get a new port (suggest 8097 — currently channel-monitor, or 8105+ which are unallocated).

### 5. CHIT CGP Spec Version (affects #905, #916)

- #905 uses `chit.cgp.v0.1` (non-canonical)
- #916 documents `chit.cgp.v1.0` (canonical per CLAUDE.md)
- Existing context files use `v0.1`/`v0.2`

Need to align all to `chit.cgp.v1.0` and update context files.
