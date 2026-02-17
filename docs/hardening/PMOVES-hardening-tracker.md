# PMOVES Hardening Tracker

Status snapshot and to-dos to align with `PMOVES.AI-Edition-Hardened-Full.md`.

## Recently done (2026-02-16 — Phase C Audit)
- **Phase C audit complete**: 8 critical production submodules audited across 8 security dimensions
- **10 P1 issues identified**: Agent Zero root containers, HiRAG Cypher injection, BoTZ JWT fail-open, DoX unauthenticated NATS, tensorzero provider-proxy root, default credentials across 6 submodules
- **Cross-cutting patterns found**: NATS auth missing (all 8), env.shared export syntax (5/8), default creds (6/8)
- **Jan 28 P2 items resolved**: Open-Notebook USER ✅ (opennotebook:1000), PMOVES.YT USER ✅ (pmoves:65532)
- **PR merges**: #633 (codex consolidation), #634 (gitlinks), #642 (CI triggers), #644 (mesh namespace) — all merged to Hardened
- **Hyperdimensions**: 10 topology PRs (#2-#11) merged
- **Orphaned gitlinks**: `pmoves-e2b-mcp-server` cleaned up (`git rm --cached`)

## Previously done (2025-12 through 2026-01)
- Hardened CI now builds/scans `pmoves-yt` multi-arch (amd64+arm64) in `.github/workflows/self-hosted-builds-hardened.yml`.
- Added arm64 compose override `pmoves/docker-compose.arm64.override.yml` for Jetson/edge deployments.
- Documented Claude CLI hooks and current hardening state in `AGENTS.md`.
- Removed vendored `PMOVES.YT/yt_dlp` (pmoves-yt now pulls yt-dlp from pip build arg). Removed legacy PEM test fixtures (YT/Tailscale) that were triggering secret scans.
- Added weekly yt-dlp bump workflow (`.github/workflows/yt-dlp-bump.yml`) to keep pmoves-yt aligned with upstream.
- Trivy gating (HIGH/CRITICAL -> fail) is active in hardened self-hosted builds; SARIF uploaded to GitHub Code Scanning.
- GPU/arm64 builds wired for multi-arch; override compose validated on Jetson path.
- ✅ Regenerated `agent-zero` and `media-video` locks on Python 3.11 (CUDA cu121 wheels) with hashes.
- ✅ Loki `/ready` returns 200 (`make -C pmoves loki-ready`).

## High-priority next steps (Phase C P1 — Security Critical)

### 1. Dockerfile USER Directives (Root Containers)
| Service | File | Fix |
|---------|------|-----|
| Agent Zero (base) | `docker/base/Dockerfile` | Add `USER agentuser:1000` |
| Agent Zero (run) | `docker/run/Dockerfile` | Add `USER agentuser:1000` |
| Agent Zero (local) | `DockerfileLocal` | Add `USER agentuser:1000` |
| tensorzero provider-proxy | `provider-proxy/Dockerfile` | Add USER directive |
| BoTZ cipher | Cipher Dockerfile | Add USER directive |

### 2. Authentication Fixes
| Service | Issue | Fix |
|---------|-------|-----|
| BoTZ MCP Bridge | JWT fails open when `JWT_SECRET` unset (`auth.py:59-61`) | Fail-closed: `raise HTTPException(500)` |
| Open-Notebook | Auth bypassed when password unset (`auth.py:29`) | Fail-closed: `raise HTTPException(401)` |
| DoX NATS | No auth block in `nats.conf` | Add authorization block with credentials |

### 3. Injection & Credential Issues
| Service | Issue | Fix |
|---------|-------|-----|
| HiRAG | Neo4j Cypher injection via f-string labels (`gdb_neo4j.py:224,236,256-268`) | Parameterized queries or label allowlist |
| HiRAG | Default creds `neo4j:neo4j`, `minioadmin:minioadmin` in envared | Use `${VAR:?must be set}` |
| tensorzero | ClickHouse `tensorzero:tensorzero` in env.tier-llm | Rotate + require via `:?` |
| Open-Notebook | SurrealDB `root:root` in .env.example | Use placeholder + fail if unset |

### 4. NATS Auth (Cross-Cutting — All Submodules)
Every submodule defaults NATS URL to `nats://nats:4222`. Fix all to `nats://nats:pmoves@nats:4222`:
- Agent Zero: `pmoves_announcer/__init__.py:146`, `pmoves_health/__init__.py:146`
- HiRAG: envared
- BoTZ: `docker-compose.yml:77`
- tensorzero: env defaults
- DoX: `env.shared`
- Open-Notebook: `pmoves_announcer/__init__.py:158`
- PMOVES.YT: `yt.py:290`

### 5. env.shared export Syntax (Cross-Cutting)
Strip `export` prefix from env files in: HiRAG, BoTZ, tensorzero (env.tier-llm), DoX

## Medium-priority next steps (Phase C P2)

1. **HiRAG**: Build FastAPI wrapper service (currently library-only, no API endpoint)
2. **HiRAG**: Add /metrics Prometheus endpoint
3. **BoTZ**: Add auth middleware to MCP Gateway (`/call`, `/mcp`, `/tools` endpoints)
4. **tensorzero**: Evaluate 4 suppressed RUSTSEC advisories in `deny.toml`
5. **DoX**: Enable TLS for NATS WebSocket listener
6. **Open-Notebook**: Add /metrics endpoint, rename /health → /healthz
7. **PMOVES.YT**: URL-encode Supabase filter parameters (`yt.py:828-835`)
8. **PMOVES.YT**: Handle Supabase API errors (don't continue silently)

## Remaining from earlier audits

1. Image pinning & freshness
   - Pin remaining image tags as releases land; `flight-check` now warns on `:pmoves-latest`.
2. Secret handling SOP
   - Keep allowlist minimal; rotation checklist lives in `docs/SECRETS_ONBOARDING.md`.
3. Rerank GPU smoke
   - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` passes, but `cuda:false` in stats indicates CPU fallback; ensure NVIDIA runtime exposure on GPU hosts.
4. Add /metrics to PMOVES-Wealth (Laravel) and PMOVES-Danger-infra (Go)
5. Switch Hi-RAG v2 to `:pmoves-hardened` tag (blocked: no Dockerfile exists yet)

## Optional / nice-to-have
- Compose profiles for split deployments (PC + Jetsons + VPS) with minimal service graphs per host.
- Add StepSecurity egress allowlists mirroring service registries per workflow job.
- Shared `pmoves-common` PyPI package to deduplicate ServiceTier/HealthStatus across submodules.
- Port registry in services-catalog.md with CI enforcement.
- Template `.gitignore` for all submodules.
- CI lint for env_file format (reject `export` prefix).

Track progress here and update timestamps when tasks complete.
**Last updated:** 2026-02-16
