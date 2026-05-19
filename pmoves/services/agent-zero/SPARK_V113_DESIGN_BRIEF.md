# SPARK v1.13 Design Brief

**Date:** 2026-05-08
**Baseline:** agent-zero v1.13 (upstream tag `v1.13`, fork branch `PMOVES.AI-Edition-v1.13`)
**Current:** PMOVES fork synced to v1.9, Dockerfile.multiarch clones by branch ref
**Research:** `/a0/usr/projects/pmoves/research/AGENT_ZERO_V113_REVIEW.md`

---

## 1. Version Delta Impact (v1.9 → v1.13)

### Breaking Changes
- **browser-use REMOVED** in v1.10 — our requirements.lock has browser-use==0.11.1 (DELETE)
- **FastMCP 2.x → 3.2.4** (breaking upgrade) — fork likely on 2.x
- **MCP → 1.27.0** (CVE-2026-32871 fix) — fork unpatched
- **Image attachments**: inline base64 rejected, file-path refs only

### New Subsystems (entirely absent from PMOVES fork)
- Built-in Playwright browser (replaces browser-use)
- LibreOffice + Xpra virtual desktop + XFCE session
- Time Travel (shadow Git snapshots)
- Universal Canvas (dockable panels, modals)
- ODF-first document handling (ODT/ODS/ODP primary)

### Already Fixed in v1.13
- **pyreqwest-impersonate==0.5.3** pinned in upstream requirements.txt — our upstream-constraints.txt pin becomes redundant after sync

### Security Fixes Missing from Fork
- CVE-2026-32871 (FastMCP path traversal)
- PTY file descriptor leak fix
- Browser stale context recovery

---

## 2. Docker Hardening Requirements

### Current Scorecard: 1/9 PASS
### Target: 7/9+ PASS

| Practice | Current | Target | Approach |
|----------|---------|--------|----------|
| Non-root user | PARTIAL (a0user after root install) | PASS | Create user early, `--chown`, drop before network services |
| Minimal base | FAIL (Kali full) | ACCEPT (intentional) | Document rationale, offer slim variant for non-sec use |
| No secrets | UNKNOWN | PASS | Audit all install scripts, secrets from env/mounts only |
| Distroless/slim | FAIL | PARTIAL | Multi-stage: Stage 2 copies only runtime artifacts |
| Layer caching | PARTIAL | PASS | Order scripts by change frequency |
| Multi-stage build | FAIL | PASS | Stage 1: build deps, Stage 2: runtime only |
| HEALTHCHECK | FAIL | PASS | `HEALTHCHECK --interval=30s --timeout=5s --retries=3` |
| COPY --chown | FAIL | PASS | All COPY use `--chown=a0user:a0user` |
| .dockerignore | PARTIAL | PASS | Comprehensive .dockerignore |

### Dockerfile.multiarch Redesign

```dockerfile
# Stage 1: Builder (has build tools, runs as root)
FROM agent0ai/agent-zero-base:latest AS builder
ARG AGENT_ZERO_REPO=https://github.com/POWERFULMOVES/PMOVES-Agent-Zero.git
ARG AGENT_ZERO_REF=PMOVES.AI-Edition-v1.13
RUN git clone --depth=1 --branch ${AGENT_ZERO_REF} ${AGENT_ZERO_REPO} /git/agent-zero
COPY services/agent-zero/upstream-constraints.txt /tmp/upstream-constraints.txt
RUN . /opt/venv-a0/bin/activate \
    && uv pip install --no-cache-dir --constraint /tmp/upstream-constraints.txt \
       -r /git/agent-zero/requirements.txt \
       -r /git/agent-zero/requirements2.txt

# Stage 2: Runtime (minimal, non-root)
FROM agent0ai/agent-zero-base:latest AS app
ARG PMOVES_UID=65532
ARG PMOVES_GID=65532
RUN groupadd -g ${PMOVES_GID} pmoves && \
    useradd -u ${PMOVES_UID} -g pmoves -m -s /bin/bash pmoves
COPY --from=builder --chown=pmoves:pmoves /opt/venv-a0 /opt/venv-a0
COPY --from=builder --chown=pmoves:pmoves /git/agent-zero /git/agent-zero
# PMOVES overlay
COPY --from=builder --chown=pmoves:pmoves services/agent-zero/requirements.txt services/agent-zero/requirements.lock ./
RUN . /opt/venv-a0/bin/activate \
    && uv pip install --no-cache-dir --constraint requirements.lock -r requirements.txt
COPY --chown=pmoves:pmoves services/agent-zero/runtime ${AGENT_ZERO_HOME}/runtime
COPY --chown=pmoves:pmoves chit /app/pmoves/chit
COPY --chown=pmoves:pmoves contracts /app/contracts
COPY --chown=pmoves:pmoves configs /app/configs
COPY --chown=pmoves:pmoves services /app/services
USER pmoves
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:5000/health || exit 1
```

---

## 3. Venv and Prerequisites

### Requirements
- All tools from v1.13 must work: Playwright, FFmpeg, Tesseract, LibreOffice, Xpra
- Playwright browsers installed (Chromium)
- System packages match upstream base image
- PMOVES additions (prometheus-client, fastapi, nats-py) install cleanly

### Validation Strategy
- `uv venv --python 3.12` creates isolated venv matching CI Python version
- `uv pip install -r upstream-requirements.txt` with constraint validates transitive deps
- `uv pip install -r requirements.txt --constraint requirements.lock` validates PMOVES overlay
- Playwright: `playwright install chromium` + `playwright install-deps`
- LibreOffice/Xpra: system package install (dpkg -l | grep verification)

### upstream-constraints.txt Evolution
- After v1.13 sync, pyreqwest-impersonate pin is redundant (upstream pins it)
- Keep file as pattern for future broken transitive deps
- Add comment: "v1.13+ pins pyreqwest-impersonate==0.5.3 natively; keep file for future pins"

---

## 4. PMOVES Memory Services via Submodule

### Requirement
Sidecar and main agent must use PMOVES services for memory, loaded and available via repo submodule.

### Design
```
PMOVES.AI repo (superproject)
├── pmoves/services/agent-zero/        # SPARK integration
├── pmoves/services/common/           # Shared PMOVES services (memory, chit, etc.)
└── submodules:
    └── PMOVES-Agent-Zero → branch PMOVES.AI-Edition-v1.13
        ├── pmoves_common/             # Submodule has its own copy
        ├── pmoves_health/              # Health check endpoints
        └── chit/                       # CHIT transformation knowledge
```

### Integration Points
- Dockerfile COPY brings `pmoves_common/`, `pmoves_health/`, `chit/` into container
- `PYTHONPATH="/app:/app/services"` makes `from pmoves.services.common import memory` work
- Memory backend configurable via env: `PMOVES_MEMORY_BACKEND=nats|supabase|local`
- Sidecar connects to PMOVES NATS bus for memory pub/sub

---

## 5. Atomic Commits and Targeted PRs

### PR Sequence (each independently mergeable)

| # | PR Title | Scope | Checks |
|---|----------|-------|--------|
| 1 | `fix(ci): upstream-constraints.txt for Stage 1 transitive deps` | Dockerfile.multiarch only | Validate agent-zero |
| 2 | `chore: update .a0-upstream-version to v1.13` | Version pin file only | merge-gate |
| 3 | `feat(docker): SPARK v1.13 multi-stage hardened Dockerfile` | Full Dockerfile redesign | Validate agent-zero, hardening-validation |
| 4 | `feat(services): PMOVES memory backend integration for SPARK` | Python services + Dockerfile overlay | python-tests, Validate agent-zero |
| 5 | `ci(auto-update): agent-zero upstream version check workflow` | GitHub Actions workflow | merge-gate |
| 6 | `docs: SPARK v1.13 bring-up guide` | Documentation only | merge-gate |

### PR #1 is already open (#1433) — needs rebase after #3
### PR #5 was already created (untracked on main) — needs separate PR

---

## 6. Files to Create/Modify

### Create
- `pmoves/services/agent-zero/SPARK_V113_DESIGN_BRIEF.md` (this file)
- `pmoves/services/agent-zero/upstream-constraints.txt` (already exists in PR #1433)
- `.github/workflows/agent-zero-upstream-check.yml` (already created, needs PR)
- `pmoves/services/agent-zero/.a0-upstream-version` (already updated to v1.13)

### Modify
- `pmoves/services/agent-zero/Dockerfile.multiarch` — full redesign per §2
- `pmoves/services/agent-zero/requirements.txt` — remove browser-use, update for v1.13
- `pmoves/services/agent-zero/requirements.lock` — regenerate for v1.13 deps
- `pmoves/services/agent-zero/Dockerfile` — compose variant hardening
- `docker-compose.agents.yml` or `docker-compose.pmoves.yml` — HEALTHCHECK

### Delete
- `pmoves/services/agent-zero/requirements.lock` entry: `browser-use==0.11.1`

---

## 7. Local Validation Checklist

Before any PR:
- [ ] `uv venv /tmp/spark-test --python 3.12` succeeds
- [ ] `uv pip install --constraint upstream-constraints.txt -r <upstream-requirements.txt>` resolves
- [ ] `uv pip install --constraint requirements.lock -r requirements.txt` resolves
- [ ] `playwright install --dry-run chromium` shows correct version
- [ ] Dockerfile `COPY` paths match CI build context (`services/agent-zero/...`)
- [ ] HEALTHCHECK curl command syntax valid
- [ ] USER directive before any EXPOSE or CMD
- [ ] No ARG default contains secrets
- [ ] .dockerignore excludes .git, __pycache__, *.pyc, tests, docs

---

## 8. Fork Sync Prerequisites

Before SPARK v1.13 can build, the PMOVES-Agent-Zero fork must be synced:
1. Create branch `PMOVES.AI-Edition-v1.13` from upstream `v1.13` tag
2. Cherry-pick 28 clean overlay commits
3. Re-implement 6 conflicting files for v1.13 architecture
4. Update `conf/model_providers.yaml` for new YAML schema
5. Update `run_ui.py` Prometheus metrics for v1.13 architecture
6. Update `requirements.txt` with PMOVES additions (prometheus-client, fastapi, nats-py)
7. Update `docker/run/Dockerfile` hardening for new install scripts
8. Update `.github/` CI for new workflows
9. Set `PMOVES.AI-Edition-v1.13` as GitHub default branch

Estimated: 12-16 hours (per research report)

---

## 9. Out of Scope

- Fork sync execution (separate task, requires manual verification of 24 overlays)
- LibreOffice/Xpra/XFCE desktop subsystem tuning (defer to post-sync)
- Time Travel workspace integration
- Agent Profile switcher customization
- ChatGPT/Codex OAuth integration
