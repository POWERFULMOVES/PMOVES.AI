# PMOVES Hardening Tracker v4.0

Comprehensive hardening posture, CI/CD build infrastructure, and service runtime status for the PMOVES.AI platform.

Last updated: 2026-03-26

Live snapshot (2026-03-04): `PMOVES.AI` open PRs `0`, CodeQL open alerts `0`, Dependabot open alerts `1` (`medium`). Use `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md` as the source-of-truth for live counters.

---

## Hardening Scorecard

| Category | Coverage | Status |
|----------|----------|--------|
| **P1 Security Issues** | 0 remaining (10/10 fixed) | CLEAR |
| **CodeQL High-Severity** | 0 open CodeQL alerts (live snapshot 2026-03-04) | CLEAR |
| **Dependabot High** | 0 open high-severity Dependabot alerts (live snapshot 2026-03-04) | CLEAR |
| **Non-Root Users (USER directive)** | 29/29 services (100%) | COMPLETE |
| **Read-Only Filesystems** | 30/30 services (100%) | COMPLETE |
| **Cap Drop ALL** | All services including nats-init | COMPLETE |
| **no-new-privileges** | All services including nats-init | COMPLETE |
| **HEALTHCHECK in Dockerfile** | 12/47 (25%) | PARTIAL |
| **SHA-Pinned Base Images** | 0/60+ (0%) | LOW |
| **Multi-Stage Builds** | 4/47 (8.5%) | LOW |
| **P2 Open Issues** | 15 across 7 submodules | TRACKED |

---

## Docker Hardening Architecture

### Tier-Based Network Isolation (5 tiers)

| Network | Purpose |
|---------|---------|
| `pmoves_data` | Vector DBs, graph DBs, search indexes |
| `pmoves_api` | REST/GraphQL endpoints, gateways |
| `pmoves_app` | Business logic services |
| `pmoves_bus` | NATS event streaming |
| `pmoves_monitoring` | Prometheus, Grafana, Loki |

### YAML Anchor Hardening Model

Combined tier+hardening anchors in `pmoves/docker-compose.yml` (66 services):

| Anchor | Security Features |
|--------|-------------------|
| `x-tier-*-hardened-ro` | cap_drop:ALL, read_only:true, tmpfs /tmp+/var/tmp (noexec,nosuid,64m), no-new-privileges |
| `x-tier-*-hardened` | cap_drop:ALL, cap_add:[selective], no-new-privileges (RW for stateful) |
| `x-tier-data-hardened` | +CHOWN, +DAC_OVERRIDE, +FOWNER, +SETGID, +SETUID (database needs) |
| `x-tier-media-hardened` | GPU-specific caps for CUDA services |

### Base Image Distribution (47 PMOVES-native Dockerfiles)

| Base Image | Count | % |
|-----------|-------|---|
| Python 3.11-slim | 27 | 57% |
| Python 3.12-slim | 5 | 11% |
| Python 3.10-slim | 3 | 6% |
| NVIDIA CUDA | 3 | GPU |
| Google Distroless | 1 | agentgym-rl-coordinator |
| Nginx Alpine | 1 | invidious-companion-proxy |
| Other | 7 | Various |

---

## P1 Issues -- All Resolved (Phase H, 2026-02-17)

| # | Submodule | Issue | Resolution |
|---|-----------|-------|-----------|
| 1 | Agent Zero | 3x root Dockerfiles | USER a0user in all 3 |
| 2 | Agent Zero | NATS no auth | nats://nats:pmoves@nats:4222 |
| 3 | HiRAG | Cypher injection (f-string labels) | _ALLOWED_LABELS frozenset allowlist |
| 4 | HiRAG | Default creds | :? required vars |
| 5 | HiRAG | No API wrapper | Downgraded P3 (gateway serves endpoints) |
| 6 | HiRAG | No /metrics | Downgraded P3 (gateway has metrics) |
| 7 | BoTZ | JWT fails open | Raises HTTPException(500) |
| 8 | tensorzero | provider-proxy root | USER proxy directive |
| 9 | tensorzero | ClickHouse default creds | :? required vars |
| 10 | DoX | NATS unauthed | auth block in nats.conf |

---

## P2 Open Issues (15 total)

Tracked in `pmoves/docs/security/P2_SUBMODULE_TRACKER.md`.

| # | Submodule | Issue | Impact |
|---|-----------|-------|--------|
| 1 | BoTZ | MCP Gateway unauthenticated | Unprotected /call, /mcp, /tools |
| 2 | BoTZ | env.tier-agent.sh uses `export` syntax | Docker env_file incompatible |
| 3 | Open-Notebook | SurrealDB root:root default | Default creds in compose |
| 4 | Open-Notebook | Auth middleware fail-open | Bypasses auth if no password |
| 5 | Open-Notebook | /health not /healthz, no /metrics | Non-standard endpoints |
| 6 | PMOVES.YT | MinIO default creds in env | Hardcoded minioadmin |
| 7 | PMOVES.YT | Query injection risk | Unencoded Supabase params |
| 8 | DoX | NATS WebSocket no TLS | no_tls: true in standalone |
| 9 | Pipecat | No MCP tool allowlisting | Any tool callable |
| 10 | Pipecat | No Prometheus metrics | No observability |
| 11 | A2UI | env.shared uses `export` syntax | Docker incompatible |
| 12 | A2UI | NATS URL missing auth | No credentials in default |
| 13 | tensorzero | 4 RUSTSEC advisories | Suppressed in deny.toml |
| 14 | tensorzero | 30+ hardcoded secrets in examples | Example compose files |
| 15 | HiRAG | env.shared uses `export` syntax | Docker incompatible |

---

## CI/CD Build Infrastructure

### Workflows (17 total)

| Workflow | Type | Trigger |
|----------|------|---------|
| `build-images.yml` | Multi-arch matrix build (GHCR+DockerHub) | workflow_dispatch |
| `self-hosted-builds.yml` | GPU/CPU on self-hosted runners | Push + manual |
| `self-hosted-builds-hardened.yml` | Hardened builds (AI Lab) | Push + manual |
| `integrations-ghcr.yml` | Integration service builds (Cosign+SBOM+Trivy) | Push, PR, manual |
| `hardening-validation.yml` | Docker security checks (4 jobs) | Push, PR, manual |
| `codeql.yml` | Security scanning (actions/JS/Python) | Push, PR, schedule |
| `sql-policy-lint.yml` | Migration RLS validation | Auto |
| `chit-contract.yml` | CHIT geometry contracts | Auto |
| `python-tests.yml` | Unit/integration tests | Auto |
| `integration-contract.yml` | Integration overlay validation | Auto |
| `integration-gate.yml` | Hardened branch gate | PR |
| `deploy-gateway-agent.yml` | Gateway Agent deployment (AI Lab + VPS) | Push + manual |
| `env-preflight.yml` | Windows env validation | PR + manual |
| `sync-secrets-local.yml` | CGP/env secret sync | Manual |
| `webhook-smoke.yml` | Render webhook smoke test | Manual |
| `yt-dlp-bump.yml` | Weekly yt-dlp dependency bump | Schedule (Mon 08:00) |
| `python-images-toolchain-canary.yml` | Weekly pinned Python image toolchain canary (build + Trivy + PR) | Schedule (Mon 09:00) + manual |

### Build Matrix (`pmoves/images.yaml` -- 16 services)

All track `PMOVES.AI-Edition-Hardened` branch except:
- **BoTZ** and **Tailscale** track `main` branch

### Integration Matrix (`integrations-ghcr.matrix.json` -- 10 services)

Multi-arch (amd64+arm64), Cosign keyless signing, CycloneDX SBOMs, Trivy gating.
Exception: `deepresearch` is amd64-only.

### Registries
- GHCR: `ghcr.io/powerfulmoves/*`
- Docker Hub: `powerfulmoves/*`
- Multi-arch: amd64 + arm64 (with `docker-compose.arm64.override.yml`)

---

## Release Notes / CVE Funnel

Use two documentation sinks on purpose:
- `pmoves/docs/PRODUCTION_AUDIT_DASHBOARD.md`
  - live counters, open-alert snapshots, release evidence, and current blockers
- `docs/hardening/PMOVES-hardening-tracker.md`
  - recurring cadence, unresolved issue classes, and the operator policy for how signals are reviewed

### Cadence

| Cadence | Signal source | Operator action | Documentation sink |
|----------|---------------|-----------------|--------------------|
| Daily / active merge lane | Production Audit Dashboard, open PR checks, current CodeQL / Dependabot counts | Re-triage blockers, keep release lane clean, update ownership if a service group drifts | Audit dashboard first; `pmoves/docs/NEXT_STEPS.md` if priorities change |
| Weekly | `.github/workflows/codeql.yml`, `.github/workflows/yt-dlp-bump.yml`, `.github/workflows/python-images-toolchain-canary.yml`, Dependabot queue | Review new alerts/PRs, confirm image/toolchain bumps still pass the intended gates, merge or re-scope follow-ups | Hardening tracker + audit dashboard |
| Pre-release / infra touch | `make -C pmoves smoke-prod`, `make -C pmoves ghcr-prepublish-inrepo`, `make -C pmoves audit-layers-static` / `audit-layers-runtime`, `make -C pmoves ci-runners-check-strict` | Capture evidence, confirm runner capacity, close Trivy/hardening drift before promotion | Audit dashboard, plus `pmoves/docs/operations/FIRST_RUN.md` / `pmoves/docs/operations/MAKE_TARGETS.md` / `pmoves/docs/services/supabase/README.md` when command paths change |

### Current funnel components

- Code scanning:
  - `codeql.yml` provides recurring code-level CVE/security signal.
- Dependency freshness:
  - `yt-dlp-bump.yml` keeps the extractor lane current on a weekly cadence.
  - `python-images-toolchain-canary.yml` tests pinned Python image candidates weekly with a Trivy gate before opening a PR.
- Image / runtime release gates:
  - `make -C pmoves ghcr-prepublish-inrepo`
  - `make -C pmoves ghcr-prepublish-all`
  - `make -C pmoves smoke-prod`
- Data-plane operator checks:
  - `make -C pmoves supa-status`
  - `make -C pmoves bootstrap-data`
  - `make -C pmoves monitoring-smoke-prod`

The goal is to keep release-note and CVE awareness on a predictable interval instead of waiting for a feature PR to stumble into stale dependencies or hidden infra drift.

---

## Service Runtime Status

### Total Services: 66 defined in docker-compose.yml

### Service Distribution by Category

| Category | Count | Services |
|----------|-------|----------|
| Supabase stack | 7 | db, gotrue, postgrest, kong, realtime, storage, studio |
| Data stores | 4 | qdrant, meilisearch, neo4j, minio |
| Hi-RAG | 4 | v1 CPU, v2 CPU, v1 GPU, v2 GPU |
| API/utility | 4 | retrieval-eval, presign, render-webhook, model-registry |
| Workers | 6 | extract-worker, pdf-ingest, langextract, notebook-sync, session-context-worker, comfy-watcher |
| Media pipeline | 6 | ffmpeg-whisper, media-video, media-audio, pmoves-yt, bgutil-pot-provider, channel-monitor |
| NATS | 4 | nats, nats-init, nats-echo-req, nats-echo-res |
| Agents | 11 | agent-zero, archon, cipher-api, mesh-agent, botz-gateway, a2ui-nats-bridge, deepresearch, supaserch, publisher-discord, gateway-agent, github-runner-ctl |
| LLM/AI | 7 | tensorzero-clickhouse, tensorzero-gateway, tensorzero-ui, pmoves-ollama, gpu-orchestrator, evo-controller, llama-throughput-lab |
| Voice/TTS | 4 | ultimate-tts-studio, flute-gateway, tokenism-simulator, tokenism-ui |
| UI | 2 | pmoves-ui, jellyfin-bridge |
| Invidious | 6 | invidious-db, invidious-companion, invidious, grayjay-plugin-host, grayjay-server, invidious-companion-proxy |
| Infrastructure | 1 | cloudflared |

### Known Unhealthy Services (from 2026-02-07 audit)

| Service | Issue |
|---------|-------|
| channel-monitor | PostgreSQL URL using host.docker.internal |
| ultimate-tts-studio | Missing gradio[mcp] dependency |
| model-registry | Healthcheck failing |
| retrieval-eval | Missing /app/server.py |
| comfy-watcher | Missing MinIO credentials |

---

## Production Readiness Blockers

All 5 infrastructure blockers (B1-B5) resolved as of 2026-02-17. See `pmoves/docs/audit/PRODUCTION_AUDIT_BLOCKER_STATUS.md`.

### Remaining Configuration Blockers

| Blocker | Category | Status |
|---------|----------|--------|
| LLM API Keys Empty (8 keys) | CRITICAL | Requires secret injection |
| CHIT Security Disabled (passphrase/signatures) | CRITICAL | Requires configuration |
| Supabase Example JWT Secret | CRITICAL | Requires rotation |
| MinIO Secret Key Empty | HIGH | Requires secret injection |
| NATS Auth Missing (~16 services) | HIGH | Config remediation needed |

---

## CHIT Integration Coverage

| Level | Count | Services |
|-------|-------|----------|
| **None (verified -- zero chit_security imports found)** | 5 | Tokenism Simulator, Hi-RAG v2, Gateway, Neo4j Mind Map, Agent Zero |
| *(Corrected 2026-04-17: grep confirmed no crypto imports in these service directories. See research/CHIT_SECRETS_MANAGEMENT_AUDIT.md finding F-20.)* | | |
| **Partial** | 8 | A2UI Bridge, PMOVES.YT, DeepResearch, SupaSerch, Consciousness, Evo Controller, AgentGym, Flute |
| **None** | 13 | Extract Worker, PDF Ingest, FFmpeg Whisper, Media analyzers, Channel Monitor, etc. |

---

## Phase H History (2026-02-17)

### CodeQL High-Severity (19 alerts -> 0)
- [x] `py/incomplete-url-substring-sanitization` -- `credential_setup.py`: `urlparse().hostname` equality check
- [x] `py/incomplete-url-substring-sanitization` -- `migrate_tensorzero.py`: `urlparse().hostname` check
- [x] `py/clear-text-logging-sensitive-data` -- `update_env_from_cgp.py`: redacted CGP values
- [x] `py/clear-text-logging-sensitive-data` -- `credential_setup.py`: replaced value display with `***`
- [x] `py/clear-text-logging-sensitive-data` -- `credential_fetcher.py`: redacted error details
- [x] `py/clear-text-storage-sensitive-data` -- `audit_log.py`: CodeQL suppression (`_scrub_secrets()`)
- [x] `py/clear-text-storage-sensitive-data` -- `chit/__init__.py`: CodeQL suppression (CGP by-design)
- [x] `py/path-injection` -- `hf-mcp-server/main.py`: allowlist regex
- [x] `py/redos` -- `test_security_fixes.py`: CodeQL suppression (intentional test)

### CodeQL Medium-Severity (hardcoded defaults)
- [x] `pmoves-yt/yt.py`: removed minioadmin defaults
- [x] `ffmpeg-whisper/server.py`: removed minioadmin defaults
- [x] `pdf-ingest/app.py`: removed minioadmin defaults
- [x] `comfy-watcher/watcher.py`: removed pmoves/password defaults
- [x] `audit_log.py`: optimized regex to prevent ReDoS

### Dependabot High (3 alerts -> 0)
- [x] Pillow CVE-2026-25990: bumped 10.4.0 -> 12.1.1
- [x] Axios CVE-2026-25639: already at ^1.13.5

---

## Compose Cleanup (2026-02-26)

- [x] Removed duplicate `PORT=8100` in `session-context-worker` (copy-paste artifact)
- [x] Removed duplicate `PORT=8104` + stale comment in `github-runner-ctl`
- [x] Removed duplicate NATS comment in `agent-zero`
- [x] Added hardening to `nats-init` service (cap_drop:ALL, read_only, no-new-privileges, tmpfs)

---

## Recent Activity (2026-02-26 to 2026-02-28)

- **PR #715** (2026-02-26): Fixed 25 CodeQL alerts across Tiers 1+2 — SSRF (`py/full-ssrf`), path injection (`py/path-injection`), stack trace exposure (`py/stack-trace-exposure`). Groups A-E from Dashboard triage fully resolved.
- **PR #713** (2026-02-26): Hardening batch — NATS auth enforcement across services, `nats-init` service hardened with cap_drop:ALL/read_only/no-new-privileges/tmpfs, documentation brought to v4.0.
- **PR #719** (2026-02-28): Cipher MCP stdio→SSE migration, portable `sed`→`awk` in hooks, PowerShell crypto RNG for Windows, CHIT docs `:?` alignment.
- **PR #718** (2026-02-27): minimatch dependency bump in Solidity contracts.
- **Dependabot regression**: 5 new high-severity alerts appeared (serialize-javascript RCE x2, minimatch ReDoS x2, qs DoS x1) replacing the previously-cleared 3 high alerts. Total open: 7 (5H, 2L).

## Recent Activity (2026-03-05)

- Added weekly Python image toolchain canary workflow (`.github/workflows/python-images-toolchain-canary.yml`) to keep production Dockerfile pins reproducible while still testing newest `setuptools`/`wheel` releases.
- Canary gate behavior: patch candidate pins for managed GHCR Python images (`supaserch`, `deepresearch`, `pmoves-yt`, `archon`) -> build `linux/amd64` -> Trivy HIGH/CRITICAL gate (`ignore-unfixed=true`) -> open/update PR only on pass.
- Added operator runbook: `docs/hardening/PYTHON_IMAGES_TOOLCHAIN_CANARY.md`.
- Added local production GHCR matrix validator (`pmoves/tools/ghcr_local_prepublish.py`) with operator targets:
  - `make -C pmoves ghcr-prepublish-inrepo` (default production gate)
  - `make -C pmoves ghcr-prepublish-all` (includes external integration repos)
  - `make -C pmoves ghcr-dispatch-all` (full matrix dispatch after local gate)

---

## Gaps & Recommended Next Steps

### Quick Wins (Low Effort, High Value)
1. **Fix 5 unhealthy services** -- resolve config issues for channel-monitor, model-registry, retrieval-eval, comfy-watcher, ultimate-tts-studio
2. **Fix `export` syntax** in env files (BoTZ, A2UI, HiRAG) -- sed replacement
3. **Add NATS auth** to remaining ~16 services -- template replacement

### Medium Priority (P2 Sprint)
4. **BoTZ MCP Gateway auth** -- add middleware to /call, /mcp, /tools
5. **Open-Notebook auth fail-open** -- change to fail-closed
6. **PMOVES.YT query injection** -- URL-encode Supabase filter params
7. **DoX NATS TLS** -- enable TLS for WebSocket listener

### Infrastructure Improvements (P3)
8. **Expand HEALTHCHECK coverage** -- 12/47 (25%) currently, target 80%+
9. **SHA pin base images** -- 0/60+ pinned currently
10. **Multi-stage builds** -- only 4/47 services use them
11. **Evaluate distroless** for more services beyond agentgym-rl-coordinator
12. **CI lint for env_file format** -- reject `export` prefix automatically

### P3 (Existing)
1. **HiRAG**: Build dedicated FastAPI wrapper service
2. **HiRAG**: Add /metrics Prometheus endpoint
3. Image pinning & freshness for remaining services
4. Add /metrics to PMOVES-Wealth (Laravel) and PMOVES-Danger-infra (Go)
5. Switch Hi-RAG v2 to `:pmoves-hardened` tag

---

## Key File Paths

| File | Purpose |
|------|---------|
| `pmoves/docker-compose.yml` | Main compose (66 services, hardening anchors) |
| `pmoves/images.yaml` | Build matrix (16 services) |
| `docs/hardening/PMOVES-hardening-tracker.md` | This tracker (v4.0) |
| `docs/service-hardening-inventory.md` | Phase 1 inventory (29 services) |
| `pmoves/docs/security/P2_SUBMODULE_TRACKER.md` | 15 open P2 issues |
| `pmoves/docs/audit/PRODUCTION_AUDIT_BLOCKER_STATUS.md` | 5 blockers (all resolved) |
| `pmoves/tests/hardening/test_docker_hardening.py` | Validation suite (35 services) |
| `.github/workflows/hardening-validation.yml` | CI hardening checks |
| `.github/workflows/integrations-ghcr.yml` | Integration builds (Cosign+SBOM+Trivy) |
| `.github/workflows/suit-release-policy.yml` | §6.4 suit update release-notes gate |

---

## Suit Update Release Policy

**Standing rule:** Suit updates (Agent Zero hardened overlay, ClaWz profile normalization, persona/voice bindings, model routing changes) are **release concerns**, not background chores.

- Any PR that modifies files under `pmoves/config/profiles/`, `pmoves/config/agent_signatures.yaml`, or suit-related Make targets must include a release-notes entry.
- The hardening tracker scorecard above should reflect suit-update release status alongside security hardening status.
- **CI gate:** `.github/workflows/suit-release-policy.yml` enforces this rule automatically on all PRs to main.

---

**Target achieved:** 0 open P1, 0 open CodeQL alerts (live snapshot)
**Dependabot posture:** 0 open alerts (1H/17M/8L resolved in commit 21d95ef37, 2026-04-23)
**Previous version:** v3.0 (2026-02-17)
**Last updated:** 2026-04-23
