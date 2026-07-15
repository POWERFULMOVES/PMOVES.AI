# PMOVES.AI — Agent Onboarding Guide

> This `AGENTS.md` is the project-level contract for AI coding agents working in the PMOVES.AI monorepo. It assumes you know nothing about the project. For session-specific bootstraps, see `.claude/BOOTSTRAP.md` (Claude Code) and `.kimi/AGENTS.md` (Kimi Code CLI).

This repository follows the **[agents.md open format](https://agents.md)**. The PMOVES fork of the format spec and canonical taxonomy live in the `PMOVES-agents.md/` submodule.

---

## 1. Project Overview

**PMOVES.AI** is a modular, multi-agent AI platform built as a **submodule monorepo**. It is developed by Cataclysm Studios Inc. and organized around a **rooms-on-a-stage** topology:

- **Room** — an audience-facing topology/entry point (e.g., `4090-field.room.control`, `5090-voice.room.studio`).
- **Stage** — a lifecycle state: `rehearsal` → `live` → `review` → `archive`.
- **Suit** — a runtime binding or persona overlay for an agent.
- **P7** — the room-aware stage manager that loads `pmoves/config/rooms/catalog.json`, selects room profiles, and manages stage transitions.

The platform is designed to run across heterogeneous nodes (Z890, RTX 5090, RTX 4090 laptop, DGX Spark, Jetson, Hostinger KVM fleet, Cloudflare Edge). Nodes are treated as **capacity classes**, not fixed roles — services are brought up with node-specific Docker Compose overlays and capacity-aware Make targets.

Most capabilities are vendored as forked Git submodules under `PMOVES-*/`, while `pmoves/` holds the core orchestration workspace: the Makefile, Docker Compose files, service code, tools, tests, configuration, and documentation.

---

## 2. Repository Layout

| Path | Purpose |
|------|---------|
| `pmoves/` | Core platform: Makefile, compose files, services, tools, tests, configs, docs. |
| `PMOVES-*/` | Git submodules for major capabilities (Agent-Zero, Archon, HiRAG, TensorZero, Supabase, etc.). |
| `deploy/` | Deployment artifacts: sidecar, K8s kustomize, Cloudflare Worker, self-hosted runners, provision/runbooks. |
| `.claude/` | Claude Code CLI integration: bootstrap, catalog, patterns, hooks, skills, agent definitions. |
| `.kimi/` | Kimi Code CLI configuration: `config.toml`, `mcp.json`, skills. |
| `.kilocode/` | KiloCode operator configuration and skills. |
| `CATACLYSM_STUDIOS_INC/` | Organizational knowledge base and planning material, not runtime code. |
| `skills/` | POWERFULMOVES forks of upstream agent-skill repositories. |
| `docs/` (root) | High-level documentation and architecture guides. |
| `docker/` (root) | Small profile directory; service Dockerfiles live under `pmoves/services/*/`. |
| `scripts/` (root) | Root-level automation scripts. |

### Inside `pmoves/`

```
pmoves/
├── Makefile                    # Canonical operator interface (4,000+ lines)
├── mk/                         # Makefile modules (codex, preflight, infra, GPU, MCP, etc.)
├── docker-compose*.yml         # Compose monolith + per-tier overlays
├── docker/                     # Base/cuda/web Dockerfiles
├── services/                   # ~70+ microservices (mostly Python FastAPI)
├── tools/                      # Operator CLIs and utilities (Python)
├── tests/                      # pytest unit/smoke/integration/hardening suites
├── scripts/                    # Bash/PowerShell automation
├── config/                     # Agent registry, rooms, models, fleet, MCP, NATS
├── configs/                    # YAML registries (living docs, TAC trees, skill pairings)
├── data/                       # Runtime data mounts
├── docs/                       # Living documentation
├── monitoring/                 # Prometheus/Grafana/Loki/Promtail/cAdvisor
├── nats/                       # NATS stream configuration
├── chit/                       # CHIT secrets manifests and tooling
├── ui/                         # Next.js / React / TypeScript UI
├── design/                     # Vanilla-JS design-token layer
├── supabase/                   # Supabase migrations, functions, config.toml
├── tensorzero/                 # TensorZero TOML configs
├── neo4j/                      # Cypher scripts/datasets
├── packages/                   # Internal packages (chit, ui)
├── libs/                       # Shared libraries (langextract, providers, tz_config)
└── providers/                  # Provider integrations (Anthropic, Z.AI)
```

### Python workspace

- `pmoves/pyproject.toml` is **not a distributable package**. It exists to aggregate tool configuration (pytest, coverage) and a `dev` extra. `[tool.uv] package = false` tells `uv` to manage the environment without building it.
- `pmoves/environment.yml` defines a Conda environment `pmoves-ai` on Python 3.11 with `uv`, `pip-tools`, `rich`, `typer`, `httpx`, `pydantic`, and `fastapi`.
- `pmoves/__init__.py` bootstraps `pmoves` as a namespace package so `pmoves.services` and `pmoves.tools` are importable.

---

## 3. Technology Stack

The checked-out code is **predominantly Python** with a **TypeScript/JavaScript** UI layer. Once submodules are initialized, the repo also includes **Rust** (TensorZero), **Go** (Tailscale/Headscale), **C#** (Jellyfin), **Java/Scala** (Neo4j), and **Dart/Flutter** (A2UI).

| Area | Technology |
|------|------------|
| Orchestration / Agent runtime | Python (Agent Zero, Archon, Botz Gateway) |
| Service framework | FastAPI + uvicorn |
| LLM gateway | TensorZero (Rust) |
| Vector / graph / search | Qdrant, Neo4j, Meilisearch |
| Object store | MinIO |
| Event bus | NATS with JetStream |
| Database / Auth / API | Supabase self-hosted (Postgres, GoTrue, PostgREST, Kong, Realtime, Storage) |
| Frontend | Next.js 16 + React 19 + TypeScript + Tailwind CSS |
| Design tokens | Vanilla ESM JS (`pmoves/design/`) |
| Observability | Prometheus, Grafana, Loki, Promtail, cAdvisor, Jaeger/OTLP |
| Packaging / env | `uv`, Conda, Docker, Docker Compose |
| CI / CD | GitHub Actions, self-hosted runners, GHCR |
| Voice / media | Pipecat, ComfyUI, FFmpeg/Whisper, Jellyfin |

---

## 4. Core Platform & Runtime Architecture

The runtime is a **tiered service mesh** brought up with Docker Compose. Services are grouped by the 7 canonical service tiers defined in `pmoves/config/agent_registry.yaml`:

| Tier | Type | Element | Examples |
|------|------|---------|----------|
| 1 | `data` | Earth | Qdrant, Neo4j, Meilisearch, MinIO, Supabase |
| 2 | `api` | Water | Kong, PostgREST, Presign, Botz Gateway |
| 3 | `llm` | Fire | TensorZero Gateway, Ollama, vLLM |
| 4 | `worker` | Electric | Extract Worker, LangExtract, DeepResearch, SupaSerch |
| 5 | `media` | Wind | FFmpeg-Whisper, ComfyUI, Pipecat/Flute, TTS studios |
| 6 | `agent` | Psychic | Agent Zero, Archon, Cipher Memory, Hi-RAG v2 |
| 7 | `ui` | Light | PMOVES UI, Tokenism UI, Invidious, Grayjay |

### Key services (selected)

| Service | Port | Health | Notes |
|---------|------|--------|-------|
| Agent Zero | `:8080` API, `:8081` UI | `/healthz` | MCP API at `/mcp/*` |
| Archon | `:8091` API, `:3737` UI | `/healthz` | Supabase-driven agent service |
| Hi-RAG v2 CPU | `:8086` | `/healthz` | Preferred RAG gateway |
| Hi-RAG v2 GPU | `:8087` | `/healthz` | Cross-encoder rerank |
| TensorZero Gateway | `:3030` | `/healthz` | LLM provider gateway |
| Cipher Memory | `:8105` | `/health` | SSE MCP at `/mcp/sse` |
| Botz Gateway | `:8054` | `/healthz` | REST + NATS work-item dispatch |
| NATS | `:4222`, `:9223` | `/varz` | JetStream event bus |
| Supabase Kong | `:8000` | `/health` | API gateway |
| Neo4j | `:7474` / `:7687` | `GET /` | Graph DB |
| Qdrant | `:6333` | `/healthz` | Vector DB |
| Meilisearch | `:7700` | `/health` | Full-text search |
| MinIO | `:9000` / `:9001` | `/minio/health/live` | S3-compatible store |

The full service catalog is in `.claude/CATALOG.md`.

### Compose overlays

- `pmoves/docker-compose.yml` is the **monolithic source of truth**.
- Split overlays (`base`, `core`, `agents`, `workers`, `media`, `ui`, `apps`) are generated from it by `scripts/split_compose.py`. A pre-commit hook regenerates them; `make compose-split-check` gates drift.
- Default `STACK_FILES` always loads `docker-compose.yml` plus optional overlays such as `comfyui`, `ultimate-tts-studio`, and `archon.submodule`.
- Node-specific overlays exist for `z890`, `laptop-4090`, `arm64`, `vps`, and `spark-sidecar`.
- Networks are isolated into `pmoves_data`, `pmoves_api`, `pmoves_app`, `pmoves_bus`, `pmoves_monitoring`, and `pmoves_public`.

---

## 5. Agents, Rooms & Topology

### Agent registry

`pmoves/config/agent_registry.yaml` is the **single source of truth** for agents. It defines:

- **Classes**: `legendary` (`POWERFULMOVES`), `standard` (`PMOVES-`), `specialized` (`Pmoves-`), `utility` (`pmoves-`).
- **Types / 7 tiers**: `data`, `api`, `llm`, `worker`, `media`, `agent`, `ui`.
- **Role classes** (Three-Body pattern): `planner`, `worker`, `reviewer`.
- Per-agent entries: `port`, `health`, `layers`, `evolution_stage`, `nats` pub/sub subjects, `chit_toggles`, `topology`, and optional `submodule`.

### Rooms

`pmoves/config/rooms/catalog.json` defines 9 rooms, including:

- `4090-field.room.control`
- `5090-voice.room.studio`
- `z890-infra.room.fabric`
- `5090-kilocode.room.studio`
- `demo.room.rehearsal`
- `hermes-agent.room.control`
- `fordham.room.community`
- `darkxsides.room`
- `tokenism.room.exchange`

### Three-Body / Village Rule

The project uses a Three-Body governance model:

- **Delivery Body** — executes code changes (worker role).
- **Control Body** — plans and reviews (planner/reviewer roles).
- **Memory Body** — CHIT/Cipher custody and signed trails.

**Village Rule**: no agent operates alone in production validation. Claims, work, signatures, and releases are recorded in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`.

### Signing & personas

- `pmoves/config/signing_identity_cards.yaml` defines CHIT signing cards.
- `pmoves/config/agent_signatures.yaml` maps glyphs/colors/voices.
- `pmoves/docs/AGENTS/PERSONAS.md` documents the persona schema and seed personas.

---

## 6. Build, Runtime & Test Commands

All substantive Make targets live in `pmoves/Makefile` and `pmoves/mk/*.mk`. The root `Makefile` only delegates to `pmoves/` (its default goal is `update-service-docs`). Use `make -C pmoves <target>` for everything else.

### First-time / full verification

| Command | Purpose |
|---------|---------|
| `make -C pmoves first-run` | Bootstrap env, start services, run smoke tests. |
| `make -C pmoves verify-all` | Full pre-PR verification suite. |
| `make -C pmoves preflight` | Tooling sanity + env + submodule + flight checks. |
| `make -C pmoves flight-check` | Fast runtime readiness scan. |

### Environment & secrets

| Command | Purpose |
|---------|---------|
| `make -C pmoves env-setup` | Populate `env.shared` and tier env files from examples. |
| `make -C pmoves env-check` | Cross-platform environment validation. |
| `make -C pmoves secrets-funnel` | Canonical secrets pipeline (CHIT export → manifest sync → audit). |
| `make -C pmoves auth-bootstrap` | Runtime hydration + boot user + auth check. |

### Service bring-up

| Command | Purpose |
|---------|---------|
| `make -C pmoves up` | Start core data + workers via Docker Compose. |
| `make -C pmoves down` | Stop all containers. |
| `make -C pmoves up-agents-published` | Start Agent Zero + Archon from published images. |
| `make -C pmoves up-agents-ui` | Start agents + UI services. |
| `make -C pmoves up-all-new` | Observability-first full stack. |
| `make -C pmoves overlay-up-full` | Base + all 6 tier overlays (~84 services). |
| `make -C pmoves overlay-up-core` | Base + core infrastructure only. |
| `make -C pmoves overlay-up-agents` | Base + core + agents. |
| `make -C pmoves overlay-up-media` | Base + core + media. |
| `make -C pmoves overlay-up-ui` | Base + core + UI. |
| `make -C pmoves overlay-up-workers` | Base + core + workers. |
| `make -C pmoves overlay-up-bus` | NATS only (no CHIT passphrase required). |
| `make -C pmoves up-z890` | Z890 / RTX 3090 Ti node stack. |
| `make -C pmoves up-spark-sidecar` | DGX Spark sidecar. |
| `make -C pmoves up-darkxside-sidecar` | DARKXSIDE sidecar. |

### Data bootstrap

| Command | Purpose |
|---------|---------|
| `make -C pmoves supa-start` | Start Supabase stack (CLI or self-hosted Kong; controlled by `SUPABASE_RUNTIME`). |
| `make -C pmoves supabase-bootstrap` | Run migrations and seed data. |
| `make -C pmoves bootstrap-data` | Seed Neo4j, Qdrant, MeiliSearch, Supabase demo data. |

### Health, smoke & fleet

| Command | Purpose |
|---------|---------|
| `make -C pmoves smoke` | Core smoke-test suite. |
| `make -C pmoves smoke-gpu` | GPU rerank validation. |
| `make -C pmoves health-quick` / `health-check-all` | Read-only health checks. |
| `make -C pmoves health-summary` | Summarized service health. |
| `make -C pmoves fleet-status` | Tailscale nodes + relay health. |
| `make -C pmoves sign-trail SUMMARY=... AGENT=...` | CHIT-sign a Graphiti trail entry. |
| `make -C pmoves docs-reconcile` | Refresh living documents. |
| `make -C pmoves docs-reconcile-check` | Read-only living-docs freshness gate. |

### IDE launchers

| Command | Purpose |
|---------|---------|
| `make -C pmoves kimi` | Launch Kimi Code CLI with `.kimi/config.toml` and `.kimi/mcp.json`. |
| `make -C pmoves kilo` | Launch KiloCode GLM (requires extension). |

---

## 7. Environment, Secrets & CHIT

### Environment file layering

Compose loads env files in order; later files override earlier ones:

1. `pmoves/env.shared` (copy from `env.shared.example`)
2. `pmoves/env.tier-data`, `env.tier-supabase`, `env.tier-api`, `env.tier-llm`, `env.tier-worker`, `env.tier-media`, `env.tier-agent`, `env.tier-ui`
3. `pmoves/.env.local` (opt-in for compose runtime)
4. `pmoves/env.supa.runtime` (when `SUPABASE_RUNTIME=cli`)
5. `pmoves/env.tier-supabase.urlencoded`

### Setup flow

```bash
cp pmoves/env.shared.example pmoves/env.shared
# fill secrets
make -C pmoves env-setup
make -C pmoves env-check
make -C pmoves secrets-funnel
make -C pmoves auth-bootstrap
```

### CHIT & secrets pipeline

- **CHIT** = Cryptographic Handshake for Identity & Trust.
- The canonical secrets pipeline is `make -C pmoves secrets-funnel`. It lives in `pmoves/mk/codex.mk`, **not** in `pmoves/Makefile`.
- It performs: env repair → local hydrate → runtime hydrate → CHIT export → manifest sync → audit gates.
- Key files:
  - `pmoves/chit/secrets_manifest_v2.yaml` — canonical v2 manifest.
  - `pmoves/chit/secrets_manifest.yaml` — generated v1 manifest.
  - `pmoves/chit/secrets_categorization.yaml` — environment-scoped vs repository-scoped secrets.
- Use `pmoves/scripts/with-env.sh` as the canonical loader; do **not** `source pmoves/env.shared` directly.
- `CHIT_PASSPHRASE` / `CHIT_PROD_PASSPHRASE` are required by many agent services at compose interpolation time. Unsigned trail fallback is acceptable in dev, but still run `sign-trail`.

---

## 8. Development Conventions

### Code style

- **Python**: 3.11+, 4-space indentation, type hints preferred, Black formatter.
- **FastAPI routes**: `snake_case` functions; `kebab-case` only in URL paths.
- **TypeScript/JavaScript**: ESLint configuration; Next.js/React UI uses Tailwind CSS.
- **Event contracts**: filenames use `v{n}` suffix, e.g., `*.v1.schema.json`.
- **NATS subjects**: `<category>.<service>.<event>.<version>`, e.g., `ingest.file.added.v1`.
- **Modules**: keep them small and single-purpose.

### Docker service conventions

All new services must:

- Run as a non-root user (`USER pmoves` or similar).
- Expose `/healthz` and `/metrics` endpoints.
- Include the appropriate Compose profile.
- Be documented in `pmoves/docs/services/`.
- Prefer multi-stage builds.

Container hardening patterns in Compose:

- `cap_drop: [ALL]`
- `read_only: true`
- `security_opt: [no-new-privileges:true]`
- `tmpfs` for `/tmp`

### Conventional Commits

Use `type(scope): description` with types:

`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`

### Branch strategy

```
feature/*  →  PMOVES.AI-Edition-Hardened-Integrations  →  PMOVES.AI-Edition-Hardened  →  main
```

- **Target PR branch**: `PMOVES.AI-Edition-Hardened-Integrations`
- `main` — production releases.
- `PMOVES.AI-Edition-Hardened` — security-hardened staging.
- `PMOVES.AI-Edition-Hardened-Integrations` — feature aggregation / CI gate.
- Feature branch TTL: 14 days; fix/chore/docs: 7 days.
- Linear history required on `main`.

### Claiming work

Before non-trivial edits, update the Active Claim Register in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`. Follow the Village Rule: claim → work → sign → release.

---

## 9. Testing Strategy

### Test layout

Tests live under `pmoves/tests/` in:

- `unit/` — isolated unit tests.
- `smoke/` — quick health checks (5–30s).
- `integration/` — service-to-service tests (1–5m).
- `functional/` — end-to-end workflow tests (2–10m).
- `hardening/` — security/hardening validation.
- `performance/` — load benchmarks.
- `services/`, `tools/`, `a2ui/`, `ci/`, `fresh_start/`, `utils/`.

### pytest configuration

- Configured in `pmoves/pyproject.toml` (`[tool.pytest.ini_options]`); no root `pytest.ini`.
- Markers: `smoke`, `integration`, `functional`, `performance`, `slow`, `gpu`.
- `asyncio_mode = "auto"`.
- `addopts` includes `--import-mode=importlib`, `-v`, `--tb=short`, `--strict-markers`.
- `pmoves/tests/conftest.py` stubs heavy optional dependencies so tests can run without GPU/DB.
- `pmoves/tests/smoke/conftest.py` auto-skips Docker-required tests when Docker is unavailable.

### Running tests

```bash
# Full verification suite
make -C pmoves verify-all

# Core smoke tests
make -C pmoves smoke

# GPU rerank validation
make -C pmoves smoke-gpu

# pytest across the workspace
pytest pmoves/tests/

# Unit tests only
pytest -q pmoves/tests/unit/

# Per-service tests
pytest pmoves/services/<service>/tests/
make <service>-smoke
```

### PR requirements

- Every PR must include a **Testing** section (see `.github/pull_request_template.md`).
- Run relevant smoke targets and document results.
- Docstring coverage ≥ 80% on new Python (enforced by CodeRabbit).
- Update docs/schemas when interfaces change.

---

## 10. Security & Hardening

### Secrets discipline

- **Never commit secrets.** Copy `pmoves/env.shared.example` → `pmoves/env.shared`.
- Shared defaults go in `env.shared`; machine-specific overrides go in `.env.local`.
- Production secrets live in GitHub Actions secrets and the team vault.
- Use only the canonical pipeline: `make -C pmoves secrets-funnel`.

### CHIT & provenance

- CHIT provides cryptographic identity, trust, and provenance.
- Sign trails with `make -C pmoves sign-trail SUMMARY=... AGENT=...`.
- CHIT signing-card definitions are in `pmoves/config/signing_identity_cards.yaml`.

### Container hardening

- All services run **non-root**.
- Compose uses hardening YAML anchors (`x-hardening` for read-only, `x-hardening-rw` for stateful).
- `cap_drop: ALL`, `no-new-privileges:true`, tmpfs `/tmp`.
- Base images should be SHA-pinned where possible.

### Damage-control hooks

`.claude/hooks/` enforces guardrails:

- `bash-tool-damage-control.py` blocks dangerous shell commands.
- `edit-tool-damage-control.py` protects zero-access and read-only paths.
- `patterns.yaml` blocks destructive patterns (raw `docker system prune`, `DROP DATABASE`, etc.).
- `pre-tool.sh` / `post-tool.sh` add pre/post execution guards and NATS telemetry.

### Protected paths

- **Zero-access**: `.env*`, `~/.ssh/`, `~/.aws/`, `*.pem`, `pmoves/env.shared`, `pmoves/env.tier-*`, `pmoves/chit/*.key`.
- **Read-only**: `pmoves/docker-compose*.yml`, `pmoves/supabase/migrations/`, `.claude/context/`, `*.lock`, `dist/`, `node_modules/`.
- **No-delete**: `CLAUDE.md`, `README.md`, `.git/`, `.github/`, `pmoves/data/`, `pmoves/services/`.

### CI security gates

Required checks include:

- `CodeQL`
- `CHIT Contract Check`
- `SQL Policy Lint`

Additional workflows run Trivy SARIF scans (HIGH/CRITICAL gates), hardening validation, Docker Bench, and CodeQL for Python/JavaScript/Actions.

---

## 11. Deployment & Operations

### Deployment modes

| Mode | Entry point | Use case |
|------|-------------|----------|
| **Compose (production)** | `pmoves/docker-compose*.yml` | Full stack on bare metal / VPS. |
| **Sidecar** | `deploy/sidecar/README.md` | Standalone Agent Zero on any device. |
| **Kubernetes** | `deploy/k8s/` | Kustomize overlays (`ai-lab`, `kvm4`, `local`). |
| **Cloudflare Edge** | `deploy/cloudflare/` | Worker router (`worker.js`, `wrangler.toml`). |

### Sidecar quick start

```bash
bash deploy/sidecar/scripts/sidecar-host-prep.sh
# run the printed docker run command
```

Uses Ollama local (`host.docker.internal:11434`) or Z.AI cloud. The mini CLI is `python3 -m pmoves.tools.mini_cli <command>`.

### Self-hosted runners & CI

- Runner setup: `deploy/runners/ailab/install.sh`, `deploy/runners/vps/install.sh`.
- Build workflow: `.github/workflows/self-hosted-builds-hardened.yml` builds multi-arch images, runs Trivy scans, and pushes to `ghcr.io/powerfulmoves/pmoves-*`.
- Images are pinned in `pmoves/env.shared` (e.g., `AGENT_ZERO_IMAGE`, `ARCHON_IMAGE`).

### Operations runbooks

Key runbooks under `pmoves/docs/operations/`:

- `COMPLETE_BRING_UP_RUNBOOK.md`
- `QUICKSTART.md`
- `COMPOSE_LAYERING_RUNBOOK.md`
- `SUPABASE_OPERATIONS.md`
- `SMOKETESTS.md` / `COMPREHENSIVE_SMOKE_TESTS.md`
- `FLEET_REMOTE_ACCESS_RUNBOOK.md`
- `MCP_TOOLKIT.md`
- `DAMAGE_CONTROL_RECOVERY.md`
- `DOCKER_DAEMON_HARDENING.md`
- `PORT_REGISTRY.md`

Full Known Roads live in `.claude/PATTERNS.md § Known Roads`.

---

## 12. Documentation & Living Docs

The documentation is treated as **living documents** with freshness budgets.

| File | Purpose |
|------|---------|
| `pmoves/docs/README_DOCS_INDEX.md` | Full documentation index. |
| `pmoves/docs/SERVICE_DOCS_MATRIX.md` | Maps every service → port, docs, NATS subjects, health, audit, CHIT layer. |
| `pmoves/docs/AGENTS/README.md` | Agent overview. |
| `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` | Agent classes, tiers, evolution stages. |
| `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` | Network topology and ClaWZ integration. |
| `pmoves/docs/AGENTS/PERSONAS.md` | Persona schema and seed personas. |
| `pmoves/docs/AGENTS/AGNOTE4482.md` | P7 stage manager / Three-Body definition. |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | Active claim register. |
| `pmoves/docs/ROOMS_ON_A_STAGE.md` | Rooms/stages/suits model. |
| `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` | Room/notebook interface spec. |
| `pmoves/docs/security/` | CHIT, hardening, audit. |
| `.claude/CATALOG.md` | Service ports, URLs, health endpoints. |
| `.claude/PATTERNS.md` | Known Roads, skill pairings, damage-control recovery. |
| `pmoves/configs/living_docs_registry.yaml` | Tracked docs with freshness thresholds and severity. |

Use `make -C pmoves docs-reconcile-check` (CI-safe) and `make -C pmoves docs-reconcile` (update) to keep living docs in sync.

---

## 13. Submodule Workflow

- 53 submodules are declared in `.gitmodules`; most are `PMOVES-*/` capability forks.
- Most submodules track `PMOVES.AI-Edition-Hardened`; a few track `main`.
- Submodules are configured with `ignore = all` to prevent accidental submodule commits.
- Initialize them with:
  ```bash
  git submodule update --init --recursive
  ```
- Work in the submodule directory, land the commit there, then update the parent gitlink.
- After pointer changes, run `make -C pmoves submodule-integrity`.
- For fork-sync promotion, see `.claude/context/submodules.md` and `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/README.md`.

---

## 14. Agent-IDE Tooling Notes

These notes are shared across agent coding tools that operate on this repo.

### Installing skills

When creating or installing a new skill, place it in:

```
~/.openclaw-autoclaw/skills/<skill-name>/SKILL.md
```

The agent will discover it automatically. Do **not** install skills into `~/.agents/skills/` (shared with other tools).

### Browser automation

For any browser task, prefer **`autoglm-browser-agent`**. Fall back to Playwright or Puppeteer only if it is unavailable or fails.

### Image recognition

For image recognition tasks, prefer **`autoglm-image-recognition`**. Use the built-in image tool only as a fallback.

### Hermes evolution

Current evolution intensity for this workspace: **moderate (60%)**. When a system evolution-check message is received, evaluate and propose evolutions using the `hermes-evolution` skill at that intensity. **Never write to target files without user approval** — always use the draft/approve workflow.

When applying knowledge from a previously evolved rule, briefly echo it: "(Based on prior learning: <one-line rule summary>)".

---

## 15. Quick Reference

```bash
# First-time setup
make -C pmoves first-run

# Core data + workers
make -C pmoves up

# Agents + UI
make -C pmoves up-agents-ui

# Full overlay stack
make -C pmoves overlay-up-full

# NATS-only (no CHIT passphrase)
make -C pmoves overlay-up-bus

# Environment & secrets
make -C pmoves env-setup
make -C pmoves env-check
make -C pmoves secrets-funnel

# Bootstrap data (production default is self-hosted Kong/compose)
make -C pmoves supa-start
make -C pmoves supabase-bootstrap
make -C pmoves bootstrap-data

# Health / smoke
make -C pmoves smoke
make -C pmoves smoke-gpu
make -C pmoves health-summary

# Provenance
make -C pmoves sign-trail SUMMARY="..." AGENT="..."

# Living docs
make -C pmoves docs-reconcile-check
make -C pmoves docs-reconcile

# Tests
pytest pmoves/tests/
pytest -q pmoves/tests/unit/
make <service>-smoke

# IDE launchers
make -C pmoves kimi
make -C pmoves kilo

# Help
make -C pmoves help
```

---

*This guide is derived from the actual project files (`pmoves/Makefile`, `pmoves/pyproject.toml`, `pmoves/config/agent_registry.yaml`, `pmoves/config/rooms/catalog.json`, `CONTRIBUTING.md`, `.claude/CATALOG.md`, `.claude/PATTERNS.md`, and the compose/workflow configurations). Keep it current when those files change.*
