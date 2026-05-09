# Repository Guidelines

## Project Structure

PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**.

- **`pmoves/`** — Core platform: Makefile, docker-compose, configs, services, tools, tests, docs
- **`PMOVES-*/`** — Git submodules (Agent-Zero, Archon, ClaWZ, Creator, HiRAG, YT, supabase, etc.)
- **`pmoves/config/`** — Agent registry (`agent_registry.yaml`), model configs, TAC trees
- **`pmoves/docs/`** — Documentation (agents, operations, services, plans, security)
- **`pmoves/services/`** — Service forks and local service code
- **`pmoves/tests/`** — Unit, smoke, integration, and hardening tests
- **`deploy/`** — Deployment configs (sidecar, K8s, cloudflare, provision)
- **`.claude/`** — Claude Code context, commands, hooks, MCP config
- **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`

## Canonical Documentation

| Topic | Location |
|-------|----------|
| **Agents overview** | `pmoves/docs/AGENTS/README.md` — 71 agents, taxonomy v1.5.0, 7 tiers |
| **Agent taxonomy** | `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` — 4 classes, evolution stages |
| **Agent topology** | `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` — network topology, ClaWZ integration |
| **Agent registry** | `pmoves/config/agent_registry.yaml` — single source of truth for all agents |
| **Model integration** | `pmoves/docs/PMOVES_MODEL_INTEGRATION_FRAMEWORK.md` — model suits, routing |
| **Personas** | `pmoves/docs/AGENTS/PERSONAS.md` — persona schema, 8 seed personas |
| **Service docs matrix** | `pmoves/docs/SERVICE_DOCS_MATRIX.md` — per-service doc index |
| **Docs index** | `pmoves/docs/README_DOCS_INDEX.md` — full documentation index |
| **Operations** | `pmoves/docs/operations/` — smoketests, monitoring, runbooks |
| **Security** | `pmoves/docs/security/` — CHIT, hardening, audit |
| **Roadmap** | `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` |
| **Claude runbook** | `.claude/CLAUDE.md` — live service map and operator guide |
| **Codex operator** | `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md` — Codex-first runbook |
| **Sidecar deploy** | `deploy/sidecar/README.md` — standalone deployment on any device |

## Build & Development Commands

All make targets live in `pmoves/Makefile`. Run with `make -C pmoves <target>`.

### Common targets
- `make -C pmoves up` — Start core stack (data + workers) via Docker Compose
- `make -C pmoves down` — Stop all containers
- `make -C pmoves supa-start` — Start Supabase CLI stack
- `make -C pmoves supabase-bootstrap` — Run migrations and seed data
- `make -C pmoves bootstrap-data` — Seed Neo4j, Qdrant, MeiliSearch, Supabase demo data
- `make -C pmoves smoke` — Core smoketest suite
- `make -C pmoves smoke-gpu` — GPU rerank validation (`GPU_SMOKE_STRICT=true` for strict)
- `make -C pmoves up-agents-published` — Start Agent Zero + Archon from published images
- `make -C pmoves env-setup` — Configure environment from `env.shared`
- `make -C pmoves env-check` — Validate environment configuration
- `make -C pmoves preflight` — Tooling sanity check
- `make -C pmoves flight-check` — Runtime sanity check

### Bring-up sequence
1. `docker network create pmoves-net || true`
2. `cp pmoves/env.shared.example pmoves/env.shared` → fill secrets
3. `make -C pmoves env-setup && make -C pmoves env-check`
4. `make -C pmoves supa-start && make -C pmoves supabase-bootstrap`
5. `SUPABASE_RUNTIME=cli make -C pmoves up`
6. `make -C pmoves bootstrap-data`
7. `make -C pmoves smoke`

## Coding Style
- Python 3.11+, 4-space indentation, type hints preferred
- FastAPI routes: snake_case functions; kebab-case in URL paths only
- Event contracts: `v{n}` suffix in filenames (e.g., `*.v1.schema.json`)
- Keep modules small and single-purpose

## Testing
- Framework: `pytest` — tests per service in `pmoves/tests/` (unit, smoke, integration, hardening)
- Mock external systems (NATS, Supabase, Neo4j); validate with sample payloads
- Run: `pytest -q pmoves/tests/unit/` or per-service paths
- Local CI checks: `docs/LOCAL_CI_CHECKS.md`
- Before pushing: run relevant smoke targets and document results in PR

## Commit & PR Guidelines
- Conventional Commits: `feat(scope): description`, `fix(scope): description`, `docs(scope): description`
- PRs: clear description, linked issues, affected services, testing evidence
- Keep changes atomic; update docs/schemas when interfaces change

## Secrets
- Never commit secrets. Copy `pmoves/env.shared.example` → `pmoves/env.shared`
- Shared defaults in `env.shared`, machine-specific in `.env.local`
- Production secrets in GitHub Actions secrets and team vault
- Onboarding: `docs/SECRETS_ONBOARDING.md`

## Submodule Workflow
- Consult `.claude/context/submodules.md` and `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/README.md` before submodule changes
- Work in the submodule directory, land the commit there, then update the PMOVES.AI gitlink
- Run `make -C pmoves submodule-integrity` after pointer changes

## Deployment

### Sidecar (standalone)
Agent Zero container for deploying PMOVES on any device. See `deploy/sidecar/README.md`.
- Quick start: `bash scripts/sidecar-host-prep.sh` → run printed `docker run` command
- LLM: Ollama local (`host.docker.internal:11434`) or Z.AI cloud
- Mini CLI: `python3 -m pmoves.tools.mini_cli <command>` via `code_execution_remote`

### Compose (production)
Full stack with NATS, TensorZero, Supabase, monitoring. See `pmoves/docker-compose.yml`.
- Images pinned in `pmoves/env.shared` (`AGENT_ZERO_IMAGE`, `ARCHON_IMAGE`, etc.)
- GHCR workflow builds multi-arch images: `.github/workflows/self-hosted-builds-hardened.yml`

## Security
- CHIT (Cryptographic Handshake for Identity & Trust): `pmoves/docs/security/`
- Hardening tracker: `docs/hardening/PMOVES-hardening-tracker.md`
- Trivy scans gate on HIGH/CRITICAL in CI
- CodeQL for code scanning regressions

## AGENTS.md Format Reference

This file follows the **[agents.md open format](https://agents.md)** — a universal contract for guiding coding agents (Claude Code, Codex, Copilot, Cursor, Aider, etc.). The PMOVES fork of the format spec lives at [`PMOVES-agents.md/`](PMOVES-agents.md/) (submodule, fork of [agentsmd/agents.md](https://github.com/agentsmd/agents.md)).

The PMOVES-agents.md submodule is the canonical home for:
- AGENTS.md format reference + extensions
- Agent taxonomy & class definitions
- Persona schema and seed personas
- Universal coding-agent docs

**Tier:** *Tier-2 always-relevant* — load when discussing agent classes, taxonomy, persona schema, or AGENTS.md format itself.

**Cross-refs:** This `AGENTS.md` (project root) carries project-specific structure & commands; the format/taxonomy reference lives in the submodule. Today, taxonomy docs (`pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`, `PMOVES_AGENT_TOPOLOGY.md`) live in `pmoves/docs/`; migrating them into `PMOVES-agents.md/` is gated on explicit user confirmation since it changes git history paths.

## Skills Constellation

POWERFULMOVES forks of upstream agent-skill repositories live under [`skills/`](skills/) — see [`skills/README.md`](skills/README.md) for the full map. Currently includes Anthropic's `skills` (added) plus 4 forks pending operator approval (`PMOVES-awesome-agent-skills`, `pmoves-fork-repository-skill`, `PMOVES-agent-sandbox-skill`, `Pmoves-claude-d3js-skill`).
