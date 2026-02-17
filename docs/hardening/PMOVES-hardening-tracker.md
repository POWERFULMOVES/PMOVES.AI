# PMOVES Hardening Tracker v3.0

Status snapshot and to-dos to align with `PMOVES.AI-Edition-Hardened-Full.md`.

## Phase H: Audit Completion Sprint (2026-02-17)

### CodeQL High-Severity (19 alerts → 0)
- [x] `py/incomplete-url-substring-sanitization` — `credential_setup.py`: replaced `"ghcr.io" in registry` with `urlparse().hostname` equality check
- [x] `py/incomplete-url-substring-sanitization` — `credential_setup.py`: replaced `"docker.io" in registry` with `urlparse().hostname` check
- [x] `py/incomplete-url-substring-sanitization` — `migrate_tensorzero.py`: replaced `"ollama" in api_base` with `urlparse().hostname` check
- [x] `py/clear-text-logging-sensitive-data` — `update_env_from_cgp.py`: redacted CGP values in print output
- [x] `py/clear-text-logging-sensitive-data` — `credential_setup.py`: replaced `value[:10]...` display with `***`
- [x] `py/clear-text-logging-sensitive-data` — `credential_fetcher.py`: redacted error details, fixed value display loop
- [x] `py/clear-text-storage-sensitive-data` — `audit_log.py`: added CodeQL suppression (values scrubbed by `_scrub_secrets()`)
- [x] `py/clear-text-storage-sensitive-data` — `chit/__init__.py`: added CodeQL suppression (CGP by-design encoding)
- [x] `py/path-injection` — `hf-mcp-server/main.py`: added CodeQL suppression (allowlist regex `^[a-zA-Z0-9._-]+$`)
- [x] `py/redos` — `test_security_fixes.py`: added CodeQL suppression (intentional ReDoS test pattern)

### CodeQL Medium-Severity (hardcoded defaults)
- [x] `pmoves-yt/yt.py`: removed `"minioadmin"` default from `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`
- [x] `ffmpeg-whisper/server.py`: removed `"minioadmin"` default from `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`
- [x] `pdf-ingest/app.py`: removed `"minioadmin"` default from `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`
- [x] `comfy-watcher/watcher.py`: removed `"pmoves"/"password"` defaults from `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`
- [x] `audit_log.py`: optimized `(.|\n)*?` regex to `[\s\S]*?` to prevent ReDoS

### Dependabot High (3 alerts → 0)
- [x] Pillow CVE-2026-25990: bumped `media-video/requirements.txt` from 10.4.0 → 12.1.1
- [x] Axios CVE-2026-25639: `pmoves/ui/package.json` already at ^1.13.5 (patched version)

### Phase C P1 Resolution (10 P1 → 0)
| # | Submodule | Issue | Status |
|---|-----------|-------|--------|
| 1 | Agent Zero | No USER in 3 Dockerfiles | ✅ `USER a0user` in all 3 (on branch tip) |
| 2 | Agent Zero | NATS URL no auth | ✅ `nats://nats:pmoves@nats:4222` |
| 3 | HiRAG | Cypher injection (f-string labels) | ✅ `_ALLOWED_LABELS` frozenset allowlist added (Phase H) |
| 4 | HiRAG | Default creds | ✅ `:?` required vars |
| 5 | HiRAG | No API wrapper | Downgraded to P3 — `hi-rag-gateway/` serves endpoints |
| 6 | HiRAG | No /metrics | Downgraded to P3 — gateway has metrics |
| 7 | BoTZ | JWT fails open | ✅ raises `HTTPException(500)` |
| 8 | tensorzero | provider-proxy root | ✅ `USER proxy` |
| 9 | tensorzero | ClickHouse default creds | ✅ `:?` required vars |
| 10 | DoX | NATS unauthed | ✅ auth block in `nats.conf` |

### Phase C P2 Credential Cleanup
- [x] DoX `env.shared`: `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` → `:?` required
- [x] TensorZero `envared`: `NEO4J_USERNAME` → `:?` required (PASSWORD/MINIO already done)

## Phase G: CHIT-Distilled Models (2026-02-17)
- Model spotlight SQL migration, datasets config, publish script
- CHIT lanes routing module, model strengths seed, agent registry update

## Phase C Audit (2026-02-16)
- **Phase C audit complete**: 8 critical production submodules audited across 8 security dimensions
- **10 P1 issues identified**: Agent Zero root containers, HiRAG Cypher injection, BoTZ JWT fail-open, DoX unauthenticated NATS, tensorzero provider-proxy root, default credentials across 6 submodules
- **Cross-cutting patterns found**: NATS auth missing (all 8), env.shared export syntax (5/8), default creds (6/8)
- **Jan 28 P2 items resolved**: Open-Notebook USER ✅ (opennotebook:1000), PMOVES.YT USER ✅ (pmoves:65532)
- **PR merges**: #633 (codex consolidation), #634 (gitlinks), #642 (CI triggers), #644 (mesh namespace)
- **Hyperdimensions**: 10 topology PRs (#2-#11) merged
- **Orphaned gitlinks**: `pmoves-e2b-mcp-server` cleaned up (`git rm --cached`)

## Previously done (2025-12 through 2026-01)
- Hardened CI builds/scans `pmoves-yt` multi-arch (amd64+arm64)
- arm64 compose override for Jetson/edge deployments
- Trivy gating (HIGH/CRITICAL -> fail) active in hardened self-hosted builds
- Regenerated `agent-zero` and `media-video` locks on Python 3.11 (CUDA cu121 wheels)

## Remaining P2/P3 Items

### P2 (Medium Priority)
1. **BoTZ**: Add auth middleware to MCP Gateway (`/call`, `/mcp`, `/tools` endpoints)
2. **tensorzero**: Evaluate 4 suppressed RUSTSEC advisories in `deny.toml`
3. **DoX**: Enable TLS for NATS WebSocket listener
4. **Open-Notebook**: Add /metrics endpoint, rename /health → /healthz
5. **PMOVES.YT**: URL-encode Supabase filter parameters (`yt.py:828-835`)

### P3 (Low Priority)
1. **HiRAG**: Build dedicated FastAPI wrapper service
2. **HiRAG**: Add /metrics Prometheus endpoint (gateway has metrics)
3. Image pinning & freshness for remaining services
4. Add /metrics to PMOVES-Wealth (Laravel) and PMOVES-Danger-infra (Go)
5. Switch Hi-RAG v2 to `:pmoves-hardened` tag

## Optional / Nice-to-Have
- Compose profiles for split deployments (PC + Jetsons + VPS)
- StepSecurity egress allowlists per workflow job
- Shared `pmoves-common` PyPI package for ServiceTier/HealthStatus
- Port registry in services-catalog.md with CI enforcement
- CI lint for env_file format (reject `export` prefix)

---

**Target achieved:** 0 open P1, 0 high CodeQL, 0 high Dependabot
**Last updated:** 2026-02-17
