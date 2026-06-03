# Z890-CLAUDE Handoff — GHCR Trivy + NATS Auth Batch

**Source:** SPARK-KIMI session 2026-05-30 → Z890-CLAUDE pair-review 2026-06-01  
**PR:** #1668 (merged) + #1669 (review record, merged)  
**Scope:** Submodule-level Dockerfile base-image bumps + 111-file NATS auth batch  
**Priority:** P1 (blocks GHCR integration lane greenness)

---

## Context

PR #1668 fixed Trivy failures for **main-repo** integration lanes by adding `apt-get upgrade -y` and `pull: true`. The remaining failing lanes all live in **submodules** whose Dockerfiles reference outdated base images.

The 111-file NATS auth issue was confirmed as **main-repo clean** — all `nats://nats:4222` refs in `pmoves/` are in tests, mocks, or docs that intentionally reference the unauthenticated pattern. The actual vulnerable defaults are in submodules.

---

## Lane 1 — Submodule Base-Image Bumps (GHCR Trivy)

| Integration | Submodule | File | Current Base | CVE Count | Fix |
|-------------|-----------|------|-------------|-----------|-----|
| **archon-ui** | `PMOVES-Archon` | `pmoves/integrations/archon/Dockerfile` | `oven/bun:1.3.11-slim` | 9 HIGH / 2 CRITICAL | `oven/bun:1.3.14-slim@sha256:d56a2534ffd262e92c12fd3249d3924d296d97086da773f821d7d0477435ea04` |
| **open-notebook** | `PMOVES-Open-Notebook` | `Dockerfile` | `python:3.12-slim-bookworm` | 7 HIGH / 2 CRITICAL | `python:3.12-slim` (Debian 13 Trixie) or add `apt-get upgrade -y` |
| **tokenism-ui** | `PMOVES-ToKenism-Multi` | `pmoves-nextjs/Dockerfile` | `node:20-slim` | 4 HIGH / 2 CRITICAL OS + 11 HIGH Node | `node:22-slim@sha256:7af03b14a13c8cdd38e45058fd957bf00a72bbe17feac43b1c15a689c029c732` |
| **wger** | `Pmoves-Health-wger` | `extras/docker/production/Dockerfile` | `wger/base:latest` (stale cache) | Unknown | Rebuild `wger/base:latest` in CI before prod build, OR add `apt-get upgrade -y` in final stage |

### Submodule PR Strategy

1. **archon-ui**: Update Dockerfile in `PMOVES-Archon` submodule, push branch, open PR, bump superproject gitlink.
2. **open-notebook**: Same pattern — update Dockerfile, push, PR, bump gitlink.
3. **tokenism-ui**: Same pattern — update Dockerfile, push, PR, bump gitlink.
4. **wger**: Either rebuild base image or add `apt-get upgrade`. The base image (`wger/base:latest`) is built from `ubuntu:24.04` but not rebuilt before the prod build.

---

## Lane 2 — NATS Auth Batch Fix (~111 files)

### Pattern
Replace `nats://nats:4222` → `nats://nats:pmoves@nats:4222` in submodule source code.

### Leave Alone
- `nats://localhost:4222` — dev default, acceptable
- Test files that explicitly assert against the unauthenticated URL
- Documentation that mentions the issue

### Target Submodules (from scan)

| Submodule | Key Files |
|-----------|-----------|
| `PMOVES-BoTZ` | `pmoves_registry/__init__.py`, `pmoves_health/__init__.py`, `pmoves_announcer/__init__.py`, `features/mcp_bridge/tools/nats.py`, `features/agent_sdk/core/config.py`, `core/docker-compose/overlays/docked.yml`, `.mprocs.yaml` |
| `PMOVES-Wealth` | `pmoves_registry/__init__.py`, `pmoves_health/__init__.py`, `pmoves_announcer/__init__.py`, `docker-compose.pmoves.yml` |
| `PMOVES-DoX` | `pmoves_health/__init__.py`, `docker-compose.docked.yml`, `docker-compose.distributed.yml`, `backend/app/config.py` |
| `PMOVES-Creator` | `pmoves_registry/__init__.py`, `pmoves_announcer/__init__.py`, `pmoves_health/__init__.py`, `docker-compose.pmoves.yml` |
| `PMOVES-BotZ-gateway` | `pmoves_registry/__init__.py`, `pmoves_announcer/__init__.py`, `pmoves_health/__init__.py`, `docker-compose.pmoves.yml` |
| `PMOVES-Archon/external/PMOVES-BoTZ/*` | Same patterns as BoTZ (nested copies) |
| `PMOVES-Archon/external/PMOVES-Agent-Zero/*` | `pmoves_registry/__init__.py`, `pmoves_announcer/__init__.py`, `pmoves_health/__init__.py` |
| `Pmoves-Health-wger` | `docker-compose.yml`, `wger/utils/integration_health.py` |

### Batch-Fix Strategy

Option A (recommended): One PR per submodule → bump superproject gitlink.  
Option B: Bulk PR across multiple submodules (riskier, harder to review).

---

## Verification Checklist

- [ ] `oven/bun:1.3.14-slim` scan clean (0 HIGH / 0 CRITICAL)
- [ ] `python:3.12-slim` (Trixie) scan clean
- [ ] `node:22-slim` scan clean
- [ ] `wger/base:latest` rebuilt and scan clean
- [ ] NATS URL grep returns 0 hits for `nats://nats:4222` in production code (tests/docs exempt)
- [ ] Superproject gitlinks bumped for all modified submodules
- [ ] `integrations-ghcr.yml` run green on all 14 lanes

---

## Related

- PR #1668 (merged): Main-repo Trivy + secrets fixes
- PR #1669 (merged): Review record for #1668
- AGNOTE4482PHI.t1.md: Full agent trail context
