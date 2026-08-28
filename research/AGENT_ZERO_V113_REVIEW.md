# Agent Zero v1.13 Comprehensive Review

**Date:** 2026-05-08
**Scope:** Upstream agent0ai/agent-zero v1.9 through v1.13, PMOVES fork state
**Author:** Agent Zero Deep Research (researcher profile)

---

## Table of Contents

1. [Version Delta: v1.9 to v1.13](#1-version-delta-v19-to-v113)
2. [Current Docker Architecture](#2-current-docker-architecture)
3. [Requirements and Prerequisites](#3-requirements-and-prerequisites)
4. [PMOVES Fork State](#4-pmoves-fork-state)
5. [GitHub Docker Hardening Best Practices Assessment](#5-github-docker-hardening-best-practices-assessment)
6. [Agent Zero Instructions and Documentation](#6-agent-zero-instructions-and-documentation)

---

## 1. Version Delta: v1.9 to v1.13

### Release Timeline

| Version | Date | Commits Behind PMOVES Default Branch |
|---------|------|--------------------------------------|
| v1.9 | 2026-04-13 | 0 (synced 2026-04-25) |
| v1.10 | 2026-04-28 | ~50 |
| v1.11 | 2026-05-02 | ~90 |
| v1.12 | 2026-05-03 | ~100 |
| v1.13 | 2026-05-05 | ~140 |

### v1.9 (2026-04-13) - Security and CLI Connector

- **CVE-2026-4308:** SSRF fix in `document_query` remote fetching. Validates URLs, blocks localhost/non-public IPs, validates redirect hops, disables implicit proxy trust, enforces size cap.
- **CVE-2026-4307:** Path traversal fix in `download_work_dir_file`. Rejects requests whose resolved path escapes runtime base directory.
- **A0 CLI Connector plugin:** Built-in plugin for host-side CLI connection over authenticated HTTP/WebSocket with capability discovery, chat/context lifecycle, log streaming, remote editing, code execution, and file-tree bridging.
- **`a0-setup-cli` skill:** Guides users through host-side A0 connector setup.
- **Lexical trigger-based skill matching restored:** Lightweight trigger-word scoring re-enabled for `skills_tool:search`.
- **Native chat controls:** Telegram, WhatsApp, email threads support `/project`, `/config`, `/send`, `/queue send`.
- **Browser Agent model preset selection:** Dedicated `_model_config` preset for browser runs.

### v1.10 (2026-04-28) - The Big One: Browser, Canvas, Time Travel

**Breaking Changes:**
- `_browser_agent` removed from core (extracted as community plugin via Plugin Index)
- `browser-use` Python dependency removed
- Image attachments stored as path refs (inline base64/data-URL rejected on connector WebSocket)
- FastMCP upgraded from 2.x to 3.x

**New Features:**
- **Built-in Browser:** Direct Playwright-powered browser replacing legacy browser-use agent. Live WebUI viewer with CDP screencast streaming, floating/dockable canvas panel, tab management, Chrome extension support, annotation mode, persistent Chromium runtime.
- **ChatGPT/Codex Account OAuth:** Connect OpenAI Codex plan via device-code OAuth flow. Local OpenAI-compatible wrapper for LiteLLM. SSE streaming support.
- **Time Travel:** Shadow Git snapshots for `/a0/usr` workspaces with history, diff, preview, travel, and revert APIs. Debounced via watchdog (one snapshot per workspace every 10s).
- **Universal Canvas and dockable panels:** Browser and Office surfaces in right canvas or floating modals. Automatic canvas handoffs.
- **Office canvas:** Read/edit DOCX, XLSX, PPTX with version history, native XLSX chart creation, file tabs.
- **Agent Profile switcher:** Context-scoped profiles switchable from chat composer. Guided creation wizard.
- **Project-scoped LLM presets:** Per-project LLM configuration.

**Security:**
- **CVE-2026-32871 remediation:** FastMCP upgraded to 3.2.4, MCP to 1.27.0 for OpenAPI path-parameter traversal vulnerability.

**Infrastructure:**
- `exec_config` sent in connector WebSocket hello (removes implicit host-side Core dependency, fixes Windows remote execution)
- Stale-read protection for remote text editing
- Remote tool guidance lazy-loaded as skills
- Shell write actions blocked in read-only mode
- Text editor gains context-based `patch_text` support

### v1.11 (2026-05-02) - Multi-Tab Browser, LibreOffice Desktop

**Browser:**
- Multi-tab awareness: auto-registers popup tabs, `multi` action for parallel fan-out across tabs
- Modifier-key clicks and key chords (Ctrl+click, Meta+click, Ctrl+A, etc.)
- Shadow DOM content reading
- Screenshot previews in tool messages (clickable live thumbnails)
- Clipboard shortcuts in visual mode
- Extension management (uninstall, open UI pages)
- Cross-tab focus stability (background actions don't steal viewer focus)

**Desktop and Office - LibreOffice replaces Collabora:**
- Collabora/WOPI runtime removed
- LibreOffice + Xpra virtual desktop gateway + persistent XFCE desktop session
- Desktop document canvas: Markdown uses custom tabbed editor, DOCX/XLSX/PPTX open in full LibreOffice via Xpra
- Linux Desktop skill: XFCE/Xpra desktop operation (app launch, focus, click, typing, cell editing)
- PPTX generation through Office plugin writer
- Document rename action
- Xpra viewport stability hardening

**File Browser:** Search, bulk selection, bulk copy-paths, ZIP download, bulk delete.

**UI:** Time Travel modal-only (no longer right-canvas surface). Sidebar polish. Canvas close button.

**Fixes:** Project-level plugin config fallback, skills selector unloading, Time Travel snapshot resilience, canvas Markdown rename.

**Integrations:** Venice embedding provider. OAuth disconnect and quota visibility.

### v1.12 (2026-05-03) - Reliability and PTY Fix

- **PTY file descriptor leak fix:** POSIX PTY master descriptors properly closed on session end. Closed/exited PTY sessions detected before writes with automatic retry/recovery. Double-close prevention.
- **Browser stale context recovery:** Cached browser contexts that already closed detected before reuse. Playwright instance restarts cleanly.
- **Desktop URLs open in Agent Zero Browser:** URL clicks in Xfce route into Browser tool on opposite canvas/modal surface.
- **Self-update symlink fix:** Dangling symlinks in `/usr` logged and skipped during backup.
- **Deferred Office/Desktop startup:** Desktop starts only when Desktop surface opened or Office document created/opened. Loading indicator during Xpra init.
- **ARM64 Xpra codec gaps:** Optional local Xpra GUI client packages treated as best-effort on ARM64.

### v1.13 (2026-05-05) - ODF-First, Desktop Lifecycle, Polish

- **ODF-first document defaults:** ODT, ODS, ODP are now primary formats. OOXML (DOCX, XLSX, PPTX) available as explicit compatibility option. Full ODF package generation, validation, read/edit.
- **Unified Office canvas controls:** Active-file header in both canvas and modal views with shared "+ New" menu, inline Save, Rename/Close from dropdown.
- **Live document reload after edits:** LibreOffice-backed documents close and reopen after artifact edits.
- **Reduced automatic document triggering:** Meta-discussions about generated files no longer create artifacts.
- **Persistent Desktop lifecycle:** Single Xpra Desktop iframe stays alive across canvas, modal, and keepalive hosts. Shutdown distinguished from crashes. XFCE panel "Shutdown Desktop" launcher (requires confirmation). Unsafe logout/lock/switch-user hidden.
- **Desktop state controls:** New `desktop_state` helper, expanded `desktopctl` commands, Xpra bridge diagnostics.
- **Generalized CLI agent guidance:** Desktop skill distinguishes shell prompts from target CLI prompts. Generic nested CLI-agent launch pattern (`TARGET_CLI`/`FALLBACK_CMD`).
- **Stable modal switching:** Desktop to Browser reuses existing sessions. Focus mode control in Browser modal header.
- **Explicit screenshot and form actions:** New `browser:screenshot` action writes JPEG/PNG for `vision_load`. Extended input actions, `browser-forms` on-demand skill.
- **Unlimited canvas sizing:** Fixed right-canvas width cap removed.
- **Surface-switch buttons in modals:** Browser/Desktop switcher in modal headers.
- **Time Travel modal alignment:** Uses standard centered modal shell.
- **Bash-style chat input history:** Up/Down arrow navigation.
- **Infrastructure:** Pinned `pyreqwest-impersonate` at 0.5.3 (avoids Docker build failures from source-only 0.5.5 requiring cmake).

### Summary of Architectural Shifts (v1.9 to v1.13)

| Area | v1.9 State | v1.13 State |
|------|-----------|-------------|
| Browser | Legacy `browser-use` agent (plugin) | Built-in Playwright browser with multi-tab, CDP, extensions |
| Office | Basic DOCX/XLSX/PPTX | ODF-first (ODT/ODS/ODP primary) + LibreOffice Desktop via Xpra |
| Desktop | N/A | Persistent XFCE/Xpra desktop session with Linux Desktop skill |
| Canvas | Fixed right panel | Unlimited sizing, dockable modals, surface switching |
| Time Travel | N/A | Shadow Git snapshots with history/diff/revert |
| MCP | FastMCP 2.x | FastMCP 3.2.4 (breaking upgrade) |
| WebSocket | Legacy architecture | WsHandler/WsManager rewrite (from v1.5-v1.6) |
| Agent Profiles | Static | Context-scoped, switchable from chat composer |
| Model Config | Global only | Project-scoped LLM presets |
| CLI Connector | N/A | Built-in A0 CLI Connector plugin |
| Image Storage | Inline base64 | File-path references |
| Plugin System | Basic | Parallel scanning, Plugin Hub with "New" filter |

---

## 2. Current Docker Architecture

### Two-Image Design

Agent Zero uses a **two-image architecture**: a pre-built base image and a lightweight run overlay.

#### Base Image: `agent0ai/agent-zero-base:latest`

**Source:** `docker/base/Dockerfile`

```dockerfile
FROM kalilinux/kali-rolling

# Locale and timezone
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y locales tzdata
RUN sed -i -e 's/# \(en_US\.UTF-8 .*\)/\1/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8
RUN ln -sf /usr/share/zoneinfo/UTC /etc/localtime
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8 TZ=UTC

COPY ./fs/ /

# Split package installs for cache management
RUN bash /ins/install_base_packages1.sh
RUN bash /ins/install_base_packages2.sh
RUN bash /ins/install_base_packages3.sh
RUN bash /ins/install_base_packages4.sh
RUN bash /ins/install_python.sh
RUN bash /ins/install_searxng.sh
RUN bash /ins/configure_ssh.sh
RUN bash /ins/after_install.sh

CMD ["tail", "-f", "/dev/null"]
```

**Key observations:**
- Base: **Kali Linux Rolling** (not a minimal/slim image)
- **No USER directive** in base image (runs as root)
- **No HEALTHCHECK** instruction
- **No multi-stage build**
- Package installation split into 4 scripts for Docker layer caching
- Python installed after packages to ensure version override
- SearXNG and SSH configured in base
- `CMD ["tail", "-f", "/dev/null"]` — keepalive (base image is not directly runnable)

#### Run Image: `docker/run/Dockerfile`

```dockerfile
FROM agent0ai/agent-zero-base:latest

ARG BRANCH
RUN if [ -z "$BRANCH" ]; then echo "ERROR: BRANCH is not set!" >&2; exit 1; fi
ENV BRANCH=$BRANCH

COPY ./fs/ /

RUN bash /ins/pre_install.sh $BRANCH
RUN bash /ins/install_A0.sh $BRANCH
RUN bash /ins/install_additional.sh $BRANCH
ARG CACHE_DATE=none
RUN echo "cache buster $CACHE_DATE" && bash /ins/install_A02.sh $BRANCH
RUN bash /ins/post_install.sh $BRANCH

EXPOSE 22 80 9000-9009
RUN chmod +x /exe/initialize.sh /exe/run_A0.sh /exe/run_searxng.sh /exe/run_tunnel_api.sh /exe/trigger_self_update.sh

CMD ["/exe/initialize.sh", "$BRANCH"]
```

**Build Args:**

| ARG | Required | Default | Purpose |
|-----|----------|---------|---------|
| `BRANCH` | Yes | (none) | Upstream branch/tag to clone and install |
| `CACHE_DATE` | No | `none` | Cache buster for final install layer |

**Ports Exposed:**

| Port | Service |
|------|---------|
| 22 | SSH |
| 80 | Web UI (HTTP) |
| 9000-9009 | Various services (supervisord-managed) |

**Key observations:**
- **Single stage** build on top of base
- **No USER directive** (inherits root from base)
- **No HEALTHCHECK** instruction
- Install scripts are opaque (contents in `docker/run/fs/ins/`)
- Final CMD runs supervisord via `initialize.sh`

### PMOVES DockerfileLocal Differences

PMOVES adds a local development variant:

```dockerfile
FROM agent0ai/agent-zero-base:latest
ARG BRANCH=local
ENV BRANCH=$BRANCH

COPY ./docker/run/fs/ /
COPY ./ /git/agent-zero  # Local dev files

# ... same install scripts ...

# PMOVES hardening additions:
RUN id a0user 2>/dev/null || (groupadd -g 1000 a0user && useradd -u 1000 -g a0user -m -s /bin/bash a0user) && \
    chown -R a0user:a0user /git /exe

USER a0user  # Non-root execution
CMD ["/exe/initialize.sh", "$BRANCH"]
```

**PMOVES additions:**
- `BRANCH=local` default (vs required in upstream)
- Copies local source to `/git/agent-zero` for dev mode
- Creates `a0user` (UID/GID 1000) with ownership of `/git` and `/exe`
- **`USER a0user` directive** (non-root — Phase H security fix)
- Missing: `trigger_self_update.sh` chmod (only 4 scripts vs upstream's 5)

### No docker-compose.yml in Upstream

Upstream agent0ai/agent-zero has **no docker-compose.yml** at the repository root. Docker usage is via direct `docker build` with the run Dockerfile.

PMOVES `docker-compose.pmoves.yml` is a **YAML anchors template** only (no service definitions), providing:
- Tier-based environment loading (`env.shared` + per-tier env files)
- Health check template: `curl -f http://localhost:8080/healthz` (30s interval, 5s timeout, 3 retries)
- GPU resource template (nvidia driver, 1 device)
- Prometheus discovery labels
- Agent tier environment with `MCP_ENABLED`, `MAX_CONCURRENT_AGENTS`

---

## 3. Requirements and Prerequisites

### requirements.txt (Primary Dependencies)

**Document Processing:**
- `pypdf==6.0.0` — PDF reading
- `pdf2image==1.17.0` — PDF to image conversion
- `pymupdf==1.25.3` — PDF manipulation (MuPDF bindings)
- `pytesseract==0.3.13` — OCR (requires Tesseract system package)
- `unstructured[all-docs]==0.16.23` — Document extraction
- `unstructured-client==0.31.0` — Unstructured API client
- `lxml_html_clean>=0.4.0` — HTML cleaning (CVE-2024-52595 fix)
- `markdown==3.7`
- `markdownify==1.1.0`
- `html2text>=2024.2.26`
- `beautifulsoup4>=4.12.3`
- `newspaper3k==0.2.8`

**Browser/Automation:**
- `playwright==1.52.0` — Browser automation (replaces browser-use)
- `docker==7.1.0` — Docker SDK

**LLM/AI:**
- `faiss-cpu==1.11.0` — Vector similarity search
- `sentence-transformers==3.0.1` — Embedding models
- `tiktoken==0.8.0` — Token counting
- `kokoro>=0.9.2` — TTS
- `openai-whisper==20250625` — Speech recognition
- `langchain-core==0.3.49`
- `langchain-community==0.3.19`
- `langchain-unstructured==0.1.6`

**MCP/Integration:**
- `fastmcp==3.2.4` — MCP server framework (upgraded from 2.x)
- `mcp==1.27.0` — MCP SDK
- `fasta2a==0.5.0` — FastMCP-to-A2A bridge

**Web/Networking:**
- `flask[async]==3.0.3` — Web framework
- `flask-basicauth==0.2.0`
- `python-socketio>=5.14.2` — WebSocket
- `uvicorn>=0.38.0` — ASGI server
- `a2wsgi==1.10.8` — ASGI-to-WSGI bridge
- `wsproto>=1.2.0` — WebSocket protocol
- `paramiko==3.5.0` — SSH
- `pyreqwest-impersonate==0.5.3` — HTTP client (pinned, 0.5.5 is source-only)
- `duckduckgo-search==6.1.12`
- `soundfile==0.13.1`

**Utilities:**
- `GitPython==3.1.43` — Git operations
- `giturlparse==0.14.0`
- `pydantic==2.11.7` — Data validation
- `python-dotenv==1.1.0`
- `simpleeval==1.0.3` — Safe expression eval
- `watchdog==6.0.0` — File system monitoring
- `nest-asyncio==1.6.0`
- `psutil>=7.0.0`
- `pytz==2024.2`
- `webcolors==24.6.0`
- `pathspec>=0.12.1`
- `crontab==1.0.1` (listed 3x — merge artifact)
- `inputimeout==1.0.4`
- `ansio==0.0.1`
- `flaredantic==0.1.5`

**Email:**
- `imapclient>=3.0.1`
- `exchangelib>=5.4.3`
- `boto3>=1.35.0`

**Security Floor Pins (transitive dependencies):**
- `Pillow>=10.2.0` — heap buffer overflow, eval injection, DoS
- `nltk>=3.9.3` — RCE, code injection
- `h11>=0.16.0` — HTTP request smuggling
- `urllib3>=2.6.0` — resource exhaustion, data amplification
- `cryptography>=46.0.0` — insufficient data authenticity
- `werkzeug>=3.0.3` — RCE

**Windows-only:**
- `pywinpty==3.0.2; sys_platform == "win32"`

### requirements2.txt (LLM SDK)

```
litellm==1.79.3
openai==1.99.5
chardet<6
```

Separated for flexibility — LiteLLM proxy can run independently.

### System Tools (installed by base image scripts)

Based on the Kali base and package install scripts:
- **Playwright** + Chromium (via `playwright install`)
- **FFmpeg** (for Whisper audio processing)
- **Tesseract OCR** (for `pytesseract`)
- **SearXNG** (meta-search engine)
- **OpenSSH** (server and client)
- **LibreOffice** (for ODF/DOCX/XLSX/PPTX — added in v1.11+)
- **Xpra** (virtual desktop gateway — added in v1.11+)
- **XFCE** (desktop environment — added in v1.11+)
- **Supervisord** (process manager)
- **Git**
- **Python 3.x** (installed after system packages for version override)

### Venv Management

The base image install scripts handle Python setup. The run image's `install_A0.sh` clones the Agent Zero repo at the specified `BRANCH` and installs into what appears to be a system-wide or venv-managed Python environment. The `install_A02.sh` script does a clean reinstall without caching for build speed. Exact venv path is opaque (inside the install scripts).

### Notes on requirements.txt Quality

- **Duplicate entries:** `crontab==1.0.1` appears 3 times, `pdf2image==1.17.0` appears 2 times, `imapclient>=3.0.1` appears 2 times — merge artifacts from the rapid release cadence.
- **Mixed versioning:** Some packages pinned to exact versions (`==`), others use minimum bounds (`>=`). No upper bounds except `chardet<6`.
- **Security floor pins are good practice** but add maintenance burden.

---

## 4. PMOVES Fork State

### Repository: POWERFULMOVES/PMOVES-Agent-Zero

### Branch Status

| Branch | Status | Behind Upstream | Ahead |
|--------|--------|-----------------|-------|
| `PMOVES.AI-Edition-Hardened` | GitHub default (old fallback) | **744 commits** | 25 commits |
| `PMOVES.AI-Edition-v1.9` | Synced branch (2026-04-25) | ~140 commits (v1.10-v1.13) | 24 overlay commits |

**Critical:** The GitHub default branch `PMOVES.AI-Edition-Hardened` is the **old fallback** pinned at commit 2e000aa (Mar 7, 2026). It was NOT updated during the v1.9 sync. Anyone cloning without specifying a branch gets stale code.

The actual synced branch `PMOVES.AI-Edition-v1.9` was created on 2026-04-25 with gap closed to 0 against upstream v1.9 (commit 3fa8481b).

### PMOVES Overlay Commits (24 total, 34 files)

**28 clean cherry-picks:** PMOVES-specific additions that apply cleanly.

**6 conflicting files (re-implemented from scratch for each sync):**

| File | Conflict Severity | Content |
|------|-------------------|---------|
| `conf/model_providers.yaml` | CRITICAL | TensorZero routing, MiniMax provider (old YAML schema) |
| `run_ui.py` | CRITICAL | Prometheus metrics (+44 lines targeting deleted architecture) |
| `requirements.txt` | HIGH | `prometheus-client>=0.20.0`, `fastapi>=0.115.0` additions |
| `docker/run/Dockerfile` | HIGH | Non-root user `a0user`, NATS hardening |
| `docker/run/fs/exe/run_A0.sh` | MEDIUM | Path containment checks |
| `docs/README.md` | LOW | PMOVES branding |

### PMOVES-Specific Additions

| Directory/File | Purpose |
|----------------|---------|
| `chit/` | CHIT secrets manifest, transformation knowledge |
| `pmoves_announcer/` | NATS-based announcement service |
| `pmoves_common/` | Shared PMOVES utilities |
| `pmoves_health/` | Health check endpoints, Prometheus metrics |
| `pmoves_registry/` | Service registry |
| `conf/` | Model providers (TensorZero, MiniMax, Z.AI) |
| `scripts/` | Credential bootstrap scripts |
| `docker/` | Hardened Docker config, path containment |
| `agents/` | PMOVES custom agent profiles |
| `CLAUDE.md` | Claude Code developer context |
| `PMOVES.AI_INTEGRATION.md` | Integration documentation |
| `docker-compose.pmoves.yml` | YAML anchors template for tier-based deployment |
| `env.shared`, `env.tier-agent.sh`, `envared` | Environment configuration |
| `.github/` | PMOVES audit gate CI, NATS flag |

### Sync Gap Analysis (as of 2026-05-08)

**What PMOVES is missing from v1.10-v1.13:**

1. **Built-in Playwright browser** — PMOVES still has legacy `lib/browser/` (browser-use prototype from 2 years ago)
2. **LibreOffice/Xpra/XFCE desktop** — Entirely absent from PMOVES
3. **Time Travel** — Shadow Git workspace history
4. **Universal Canvas system** — Dockable panels, modal switching
5. **ODF-first document handling** — ODT/ODS/ODP support
6. **FastMCP 3.x** — PMOVES likely on FastMCP 2.x
7. **MCP 1.27.0** — Security fix for path-parameter traversal
8. **CVE-2026-32871 fix** — OpenAPI path traversal in FastMCP
9. **PTY fd leak fix** — Resource exhaustion prevention
10. **Agent Profile switcher** — Context-scoped profiles
11. **Project-scoped LLM presets**
12. **ChatGPT/Codex OAuth** integration
13. **CLI Connector plugin** (from v1.9)
14. **Bash-style chat input history**
15. **File browser search and bulk operations**
16. **Venice embedding provider**

**Estimated sync effort:** 12-16 hours (increased from previous 8-12 due to LibreOffice/Xpra/Desktop additions creating entirely new subsystems).

### Auto-Update CI/CD

PMOVES has a daily cron workflow at `.github/workflows/agent-zero-upstream-check.yml` (untracked on main, needs separate PR) that:
- Checks upstream releases against `.a0-upstream-version` pin file (currently `v1.9`)
- Creates draft PR on new version detection
- Polls CI and labels `ready-for-review` on pass or posts failure analysis on fail
- Never auto-merges — fork sync is manual due to 24 overlay commits + 6 conflicting files

**Known issue:** `AGENT_ZERO_REF` in Dockerfile.multiarch may point to old fallback branch `PMOVES.AI-Edition-Hardened` rather than synced `PMOVES.AI-Edition-v1.9`. Must verify post-sync.

---

## 5. GitHub Docker Hardening Best Practices Assessment

Assessment of upstream agent0ai/agent-zero Docker images against GitHub-recommended hardening practices.

### Scoring Matrix

| Practice | Upstream Base | Upstream Run | PMOVES DockerfileLocal | Status |
|----------|:------------:|:------------:|:---------------------:|--------|
| Non-root user | FAIL | FAIL | PASS | PMOVES only |
| Minimal base image | FAIL | N/A | N/A | Kali is full distro |
| No secrets in image | UNKNOWN | UNKNOWN | UNKNOWN | Opaque install scripts |
| Distroless/slim variant | FAIL | N/A | N/A | Kali rolling |
| Layer caching optimization | PASS | PARTIAL | PARTIAL | 4 split scripts in base |
| Multi-stage build | FAIL | FAIL | FAIL | None present |
| HEALTHCHECK instruction | FAIL | FAIL | FAIL | None present |
| COPY --chown | FAIL | FAIL | FAIL | No --chown flags |
| .dockerignore best practices | UNKNOWN | UNKNOWN | PARTIAL | PMOVES has .dockerignore |

### Detailed Findings

#### 1. Non-Root User — FAIL (upstream), PASS (PMOVES)

Upstream runs entirely as root. No `USER` directive in either Dockerfile.
PMOVES DockerfileLocal adds `USER a0user` (UID/GID 1000), but only after all install scripts have run as root. The install scripts themselves run with full root privileges.

**Risk:** Container escape from root is easier. Any vulnerability in Agent Zero's web server, WebSocket, or code execution tools gives full root access to the container.

**Recommendation:** Create `a0user` early in base image, use `RUN --chown=a0user` for copies, switch to `USER a0user` before any network-facing service starts. Install scripts that need root should run first, then drop privileges.

#### 2. Minimal Base Image — FAIL

`kalilinux/kali-rolling` is a full penetration testing distribution with hundreds of pre-installed security tools. This is the opposite of minimal.

**Rationale:** Agent Zero needs Kali tools for its security/hacking agent profile. This is intentional but significantly increases attack surface.

**Recommendation:** For non-security use cases, offer a `debian:bookworm-slim` or `python:3.12-slim` variant. For security use, consider `kalilinux/kali-rolling` with explicit package removal of unused tools.

#### 3. No Secrets in Image — UNKNOWN

Install scripts (`/ins/*.sh`) are opaque. Without reading their contents, cannot verify no secrets, API keys, or tokens are baked in.

**Recommendation:** Audit all install scripts. Ensure secrets come from build args, environment variables at runtime, or mounted files — never hardcoded.

#### 4. Distroless or Slim Variants — FAIL

No distroless variant exists. The full Kali image includes shell, package manager, and hundreds of tools.

**Recommendation:** For production deployments, consider a multi-stage build where Stage 1 installs everything and Stage 2 copies only runtime artifacts into a slim image.

#### 5. Layer Caching Optimization — PASS (base), PARTIAL (run)

Base image splits package installation into 4 scripts (`install_base_packages1.sh` through `install_base_packages4.sh`), which is good for layer caching — changes to one package group don't invalidate others.

Run image has a `CACHE_DATE` arg for cache busting the final install layer. However, all 5 install scripts are in sequential layers — any change to `pre_install.sh` invalidates all subsequent layers.

**Recommendation:** Order install scripts by change frequency. `pre_install.sh` (likely stable) should be first, `install_A0.sh` (changes with every branch update) should be last.

#### 6. Multi-Stage Build — FAIL

No multi-stage build in any Dockerfile. All build dependencies, install scripts, and intermediate artifacts remain in the final image.

**Recommendation:** Use multi-stage to separate build-time dependencies (gcc, cmake, build-essential) from runtime. Especially important since `pyreqwest-impersonate` 0.5.5 requires cmake compilation — build deps should not persist.

#### 7. HEALTHCHECK Instruction — FAIL

No `HEALTHCHECK` in any Dockerfile. PMOVES has a docker-compose health check template (`curl -f http://localhost:8080/healthz`) but it is not in the Dockerfile itself.

**Risk:** Orchestrators (Docker Swarm, Kubernetes, docker-compose) cannot detect unhealthy containers. A crashed supervisord or hung Agent Zero process won't trigger automatic restart.

**Recommendation:** Add to run Dockerfile:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=60s \
  CMD curl -f http://localhost:80/healthz || exit 1
```

#### 8. COPY --chown — FAIL

No `COPY --chown` used anywhere. Files are copied as root, then ownership changed (in PMOVES) via separate `chown -R` RUN command, which creates an additional layer.

**Recommendation:** Use `COPY --chown=a0user:a0user` to avoid the extra layer.

#### 9. .dockerignore Best Practices — PARTIAL

PMOVES has a `.dockerignore` file (from commit "fix skills import path and gitignores"). Upstream's .dockerignore was not inspected but likely exists.

**Recommendation:** Ensure `.dockerignore` excludes: `.git`, `node_modules`, `__pycache__`, `*.pyc`, `.env`, `venv/`, `tmp/`, `logs/`, `usr/` (runtime data), `.vscode/`, `.github/`.

### Additional Security Observations

1. **Exposed SSH (port 22):** The container runs an SSH server. Combined with root execution, this is high-risk. PMOVES should disable SSH or ensure key-only auth with `a0user`.
2. **Wide port range (9000-9009):** 10 ports exposed. Should be narrowed to only what is needed.
3. **Supervisord as init:** `CMD ["/exe/initialize.sh"]` delegates to supervisord. This is acceptable but means the container runs multiple processes (anti-pattern for containers).
4. **Self-update capability:** `trigger_self_update.sh` is baked in. In production, containers should be immutable — updates should come from new image deploys, not in-container updates.

---

## 6. Agent Zero Instructions and Documentation

### Upstream Documentation

**CLAUDE.md:** Does NOT exist in upstream agent0ai/agent-zero. This is a PMOVES-specific addition.

**CONTRIBUTING.md:** Minimal. Contains:
- Search open/recently-closed PRs before opening new ones
- Use branch matching comparable active upstream PRs
- One focused change per PR
- Maintain source branch until PR merged or closed
- Never include secrets, `.env`, local venvs, or machine-specific artifacts
- Core bugfixes go to `agent0ai/agent-zero`
- Community plugins go to `agent0ai/a0-plugins`
- Skills go to Agent Zero's `skills/` tree
- Private experiments must stay out of public forks
- Full contribution workflow at `docs/guides/contribution.md` (not inspected)
- Tests must be included with PRs or explanation of why blocked

**No SPARK-specific documentation found** in upstream.

### PMOVES CLAUDE.md (Fork-Specific)

Full developer context document for Claude Code CLI. Key sections:

**Architecture:**
- Control-plane orchestrator for PMOVES.AI multi-agent system
- Embedded agent runtime with tool execution
- MCP API for external agent integration
- NATS JetStream task coordination
- Subordinate agent creation and management
- Web UI for interactive sessions

**Subordinate Agent Model:**
1. Parent submits creation request via `/mcp/subordinate/create`
2. Agent Zero spawns subordinate with specified tools/context
3. Subordinate executes independently, reports via NATS
4. Parent retrieves results via `/mcp/task/<id>`

**Key Environment Variables:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `A0_SET_chat_model` | Primary chat model | `tensorzero::model_name::chat_default` |
| `A0_SET_utility_model` | Utility/tool model | `tensorzero::model_name::util_default` |
| `A0_SET_embedding_model` | Embedding model | `tensorzero::embedding_model_name::embed_default` |
| `A0_SET_mcp_server_token` | MCP auth token | Auto-generated |
| `MCP_CLIENT_SECRET` | External MCP client auth | Required |
| `NATS_URL` | NATS connection | `nats://nats:pmoves@nats:4222` |
| `AGENTZERO_JETSTREAM` | Enable JetStream | `true` |

**Security Posture (as documented):**
- P1 FIXED: USER directive added to all 3 Dockerfiles (Phase H, 2026-02-17)
- P1 FIXED: NATS auth credentials added
- GREEN: Secrets masking in agent output
- GREEN: CSRF protection enabled
- GREEN: `/healthz` health check endpoint
- GREEN: Prometheus `/metrics` endpoint

**MCP API Endpoints (Port 8080):**

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/healthz` | GET | No | Health check |
| `/metrics` | GET | No | Prometheus metrics |
| `/mcp/health` | GET | Bearer | MCP runtime + NATS status |
| `/mcp/commands` | GET | Bearer | List MCP commands |
| `/mcp/agents` | GET | Bearer | List agents |
| `/mcp/execute` | POST | Bearer | Submit async task |
| `/mcp/task/<id>` | GET | Bearer | Query task status |
| `/mcp/subordinate/create` | POST | Bearer | Create subordinate agent |

**NATS Subjects:**

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `agent.zero.heartbeat.v1` | Publish | Heartbeat (every 30s) |
| `agent.task.request.v1` | Subscribe | Incoming tasks |
| `agent.task.completed.v1` | Publish | Task completion |
| `agent.subordinate.created.v1` | Publish | Subordinate lifecycle |
| `agent.zero.status.v1` | Publish | Status changes |

**Common Gotchas:**
1. `tmp/settings.json` is auto-generated — don't edit manually
2. MCP token auto-generated on first run; override with `A0_SET_mcp_server_token`
3. Model names must use TensorZero format `tensorzero::model_name::name`
4. NATS URL must include credentials
5. All Dockerfiles use non-root USER directive (Phase H fix)

**Development Setup:**
```bash
cd PMOVES-Agent-Zero
pip install -r requirements.txt
python agent.py          # CLI mode
python run_ui.py         # Web UI mode
```

**Docker:**
```bash
docker compose up -d                    # Standalone
# Managed by parent docker-compose.agents.images.yml in docked mode
```

**Testing:**
```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/mcp/health -H "Authorization: Bearer $MCP_CLIENT_SECRET"
```

### PMOVES Integration Documentation

**Docked Mode (part of PMOVES.AI compose stack):**
- Compose profile: `agents`
- Ports: 8080 (API), 8081 (UI)
- Networks: `pmoves-net`, `data-net`
- Depends on: NATS (`service_healthy`), Supabase (optional)

**Archon Integration:**
- Task delegation via `/mcp/execute`
- Agent status via `/mcp/agents`
- Subordinate creation for specialized workloads

### PMOVES PMOVES.AI_INTEGRATION.md

Present in fork but content not inspected (would require separate fetch). Based on commit message, covers NATS enablement flag and PMOVES audit gate CI integration manifest.

---

## Appendix A: Sync Risk Matrix for v1.13

| Area | Risk Level | Rationale |
|------|-----------|----------|
| Dockerfile merge | HIGH | PMOVES adds USER a0user; upstream has no USER. Must re-apply. |
| requirements.txt | HIGH | PMOVES adds prometheus-client, fastapi; upstream has new deps (LibreOffice, Xpra). Conflicts certain. |
| model_providers.yaml | CRITICAL | PMOVES TensorZero/MiniMax configs use old YAML schema; upstream may have restructured. |
| run_ui.py | CRITICAL | PMOVES Prometheus metrics target architecture that may be deleted/rewritten. |
| Browser subsystem | MEDIUM | PMOVES has old browser-use; upstream has built-in Playwright. Clean replacement. |
| Desktop subsystem | LOW | Entirely new in upstream; no PMOVES conflicts. |
| MCP upgrade | HIGH | FastMCP 2.x to 3.x is breaking. PMOVES MCP integrations may need rewrite. |
| NATS integration | MEDIUM | PMOVES-specific; must re-apply after sync. No upstream conflicts expected. |

## Appendix B: Upstream CVEs Addressed in Gap

| CVE | Fixed In | Description | PMOVES Status |
|-----|----------|-------------|---------------|
| CVE-2026-4308 | v1.9 | SSRF in document_query | FIXED in v1.9 sync |
| CVE-2026-4307 | v1.9 | Path traversal in download_work_dir_file | FIXED in v1.9 sync |
| CVE-2026-32871 | v1.10 | OpenAPI path-parameter traversal in FastMCP | NOT FIXED (behind v1.9) |
| CVE-2024-52595 | requirements | XSS in lxml (lxml_html_clean pin) | Status depends on v1.9 requirements |

## Appendix C: Dependency Version Changes v1.9 to v1.13

Key dependency version differences between PMOVES v1.9 sync and upstream v1.13:

| Package | PMOVES (v1.9 era) | Upstream v1.13 | Change |
|---------|-------------------|----------------|--------|
| fastmcp | 2.x | 3.2.4 | Breaking upgrade |
| mcp | <1.27.0 | 1.27.0 | Security fix |
| pyreqwest-impersonate | variable | 0.5.3 (pinned) | Build fix |
| playwright | may be absent | 1.52.0 | New dependency |
| python-socketio | <5.14.2 | >=5.14.2 | Compat fix |
| lxml_html_clean | may be absent | >=0.4.0 | CVE fix |

---

*Report generated by Agent Zero Deep Research. All data sourced from GitHub repositories agent0ai/agent-zero and POWERFULMOVES/PMOVES-Agent-Zero on 2026-05-08.*