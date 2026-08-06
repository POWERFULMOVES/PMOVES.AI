# Repository Guidelines

## Project Structure

PMOVES.AI is a modular AI agent platform organized as a **submodule monorepo**, built on a rooms-on-a-stage topology. P7 (Pinokio 7) is the room-aware stage manager that selects rooms and manages stage transitions.

- **`pmoves/config/rooms/`** — Room catalog (`catalog.json`) and per-room manifest files — the canonical room topology
- **`pmoves/`** — Core platform: Makefile, docker-compose, configs, services, tools, tests, docs
- **`PMOVES-*/`** — Git submodules (Agent-Zero, Archon, ClaWZ, Creator, HiRAG, YT, supabase, etc.)
- **`pmoves/config/`** — Agent registry (`agent_registry.yaml`), model configs, TAC trees
- **`pmoves/docs/`** — Documentation (agents, operations, services, plans, security)
- **`pmoves/services/`** — Service forks and local service code
- **`pmoves/tests/`** — Unit, smoke, integration, and hardening tests
- **`deploy/`** — Deployment configs (sidecar, K8s, cloudflare, provision)
- **`.claude/`** — Claude Code context, commands, hooks, MCP config
- **Root** — `Makefile` (delegates to pmoves), `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`

## Operating in This Repo (Non-Obvious Rules)

These are the load-bearing conventions that are **not** obvious from reading a single file. Violating them has cost the fleet many hours. Full detail in [`.claude/PATTERNS.md`](.claude/PATTERNS.md) and [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md).

### Known Roads — dangerous ops go through Make targets

Damage-control hooks block raw `docker`, `netsh`, `tailscale`, and `gh workflow` commands and redirect to an `ask` prompt. Every dangerous-but-necessary operation has a **canonical Make target** that bypasses the hook (it encapsulates the correct stop/restart/env-injection flow). When blocked, read the prompt — it names the target.

| Raw command (blocked) | Known Road |
|---|---|
| `docker volume rm <svc>` | `make -C pmoves volume-reset SERVICE=<svc>` |
| `docker compose up -d <svc>` | `make -C pmoves up-<svc>` |
| `docker compose restart <svc>` | `make -C pmoves secrets-funnel && make -C pmoves up` |
| `tailscale status` (leaks raw IPs) | `make -C pmoves fleet-status` |
| `gh workflow run sync-secrets-local` | `make -C pmoves secrets-sync-trigger` |
| raw `-f docker-compose.<overlay>.yml up` | `make -C pmoves overlay-up-<tier>` (see layering trap below) |

Use raw commands **only** when the user explicitly directs.

### `env.shared` is Docker `env_file` format, NOT bash

Never `source pmoves/env.shared` — Windows paths and section headers will produce "command not found" errors and leave variables unset. Use the canonical loader:

```bash
bash pmoves/scripts/with-env.sh <command>          # run any command with env.shared loaded
bash pmoves/scripts/with-env.sh pytest pmoves/tests/...  # pytest with service env
```

To extract a single variable from a shell snippet: `grep '^MY_VAR=' pmoves/env.shared | cut -d= -f2 | tr -d '"'`.

### Compose overlay layering — the single-file trap

The stack is split into `docker-compose.base.yml` (networks + anchors) + 6 tier overlays (`core` / `agents` / `media` / `ui` / `workers` / `apps`). Invoking `docker compose -f docker-compose.<overlay>.yml up -d` raw fails with `service "<svc>" refers to undefined network <name>` because the base layer is missing. Always use `make -C pmoves overlay-up-<tier>` (or `overlay-up-full`). Safe read-only validation: `docker compose -f pmoves/docker-compose.<overlay>.yml config`. Full runbook: `pmoves/docs/operations/COMPOSE_LAYERING_RUNBOOK.md`.

### `secrets-funnel` is in `pmoves/mk/codex.mk`, not the root Makefile

The canonical secrets pipeline is `make -C pmoves secrets-funnel`. It is defined in `pmoves/mk/codex.mk` (included by `pmoves/Makefile`); a grep of the root `Makefile` alone returns nothing. Before adding any secrets tooling, run `grep -rn 'secrets-funnel' pmoves/Makefile pmoves/mk/`. A duplicate funnel has been written twice by agents who skipped that check.

### Three-Body / Village Rule (governance)

No agent operates alone on production validation. Every lane follows **claim → work → sign → release** in [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md) (the active claim register). Three bodies, enforced via Claude Code agent frontmatter in `.claude/agents/`: **Delivery** (edits code, `disallowedTools: EnterPlanMode`), **Control** (read-only review, `disallowedTools: Write, Edit, EnterPlanMode`), **Memory** (Cipher/CHIT only). When claiming a lane, write a `CLAIM` row with branch + scope + TTL; on completion write a `RELEASE` row and a signed ACK block.

### CHIT trail signing

After significant multi-file work, sign a provenance entry: `make -C pmoves sign-trail SUMMARY="..." AGENT=<id> PHASE="..."`. If `$CHIT_PASSPHRASE` is unset (common in dev), the payload emits **unsigned** with a stderr warning — that is expected and acceptable locally; still run it. Never hardcode passphrases.

### Damage-control hook recovery

If `patterns.yaml` ever carries unresolved merge-conflict markers, the Bash hook fails closed and blocks **all** Bash commands (you cannot even run `git status`). Recovery escape hatch: the **Edit tool** routes through a separate hook that does not depend on `patterns.yaml` parsing. Use Read + Edit to resolve the conflict markers; Bash resumes on the next call. `patterns.yaml` is intentionally not in `readOnlyPaths` so this path stays open — do not add it.

### Node identity & cross-node state

This is a multi-node fleet (Z890, 5090, 4090, SPARK, Knuckles, KVM4-1/2, KVM2, Jetsons). Per the MOF invariant (PR #1378), every node is a **pore in the lattice** — capacity-class, not expertise-lane. Always verify state locally before assuming; Claude's context is **not** consistent across nodes (different containers, worktrees, claim-register state may exist).

```bash
hostname            # which node am I on?
git branch          # what branch?
git worktree list   # am I in a worktree?
make -C pmoves fleet-status   # fleet view (no raw tailscale status — it leaks IPs)
```

Cross-node delegation: Agent Zero `POST http://localhost:8080/mcp/*` (sync), A2A `/.well-known/agent-card.json` (disabled by default), NATS `agent.peer.heartbeat.v1` (Phase D, pending).

### Progressively-disclosed context

Don't dump everything into AGENTS.md. The tiered context map:

| You want | Load |
|---|---|
| Service ports, URLs, health endpoints | [`.claude/CATALOG.md`](.claude/CATALOG.md) |
| Full Known Roads, dev patterns, CHIT, skill pairings, debug recipes | [`.claude/PATTERNS.md`](.claude/PATTERNS.md) |
| Emperor-CHIT-Humility disclosure checklist | [`.claude/BOOTSTRAP.md`](.claude/BOOTSTRAP.md) |
| Who is working on what right now | [`pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`](pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md) |
| Cold-start orientation (read this first on fresh sessions) | [`pmoves/docs/AGENTS/AGNOTE4482_SITREP.md`](pmoves/docs/AGENTS/AGNOTE4482_SITREP.md) |
| Architecture thesis | [`pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`](pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md) |


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
| **Rooms on a Stage** | `pmoves/docs/ROOMS_ON_A_STAGE.md` — end-to-end model: rooms, stages, suits, P7 role |
| **Room Manifest Contract** | `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — room/notebook interface specification |
| **P7 Stage Manager** | `pmoves/docs/AGENTS/AGNOTE4482.md` — P7 room-aware stage manager definition |
| **Room/Stage Prospectus** | `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md` — prospectus frame, foyer/war-room/voice-room model |

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
- Framework: `pytest` — tests per service in `pmoves/tests/` (unit, smoke, integration, hardening) and inline `pmoves/services/<svc>/tests/`
- Mock external systems (NATS, Supabase, Neo4j); validate with sample payloads
- Run a single service suite: `pytest -q pmoves/services/<svc>/tests/` — run under env: `bash pmoves/scripts/with-env.sh pytest pmoves/tests/unit/`
- Full verification: `cd pmoves && make verify-all` (smoke + health). Targeted: `make -C pmoves smoke`, `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu`, `make -C pmoves model-readiness`
- Docstring coverage **≥ 80%** on new Python (CI gate; enforced by CodeRabbit)
- Local CI mirror: `docs/LOCAL_CI_CHECKS.md`
- Before pushing: run `/test:pr` (or the smoke targets above) and paste a **Testing** section into the PR description
- Submodule-pointer changes: always run `make -C pmoves submodule-integrity` before/after

## Commit & PR Guidelines
- Conventional Commits: `feat(scope): description`, `fix(scope): description`, `docs(scope): description`
- Branch prefixes: `feat/`, `fix/`, `infra/`, `docs/`, `refactor/`. Forbidden: `feature/`, `pr/`, `p1`–`p7` (use workstream id). Worktrees or `feat/w<n>-...` IDs are common.
- PRs: clear description, linked issues, affected services, **Testing** section with command evidence
- Keep changes atomic; update docs/schemas when interfaces change
- Merges are **gated** — not autonomous. The standing closeout flow (`pmoves/docs/operations/PR_CLOSEOUT.md`) requires: rebased on latest main, all review threads resolved, all required CI settled, a passing live-head audit, and (where the lane touches production) a Three-Body ACK (`[ACK: delivery] [ACK: control] [ACK: memory]`) in `AGNOTE4482_SIGNOFF_CHECKLIST.md`. Use the closeout flow; do not shortcut to `gh pr merge`.
- After merging: `make -C pmoves docs-reconcile` and sign a CHIT trail entry.
- Auto-review failure signatures + merge hazards (stacked-PR auto-close, squash-merge rebase, submodule-conflict `git update-index --cacheinfo`): see [`.claude/PATTERNS.md`](.claude/PATTERNS.md) §PR Review & Merge Workflow and §Merge Hazards.

## Secrets
- Never commit secrets. Copy `pmoves/env.shared.example` → `pmoves/env.shared`
- Shared defaults in `env.shared`, machine-specific in `.env.local` (long-form `path: .env.local / required: false` in compose — the short-form `env_file: .env.local` is REQUIRED by default and hard-fails bring-up on nodes without the file)
- Production secrets in GitHub Actions secrets and team vault
- Onboarding: `docs/SECRETS_ONBOARDING.md`. Bootstrap: `make -C pmoves env-setup && make -C pmoves secrets-funnel && make -C pmoves auth-alignment`
- **Never paste API keys in chat.** Secrets flow through `env.tier-*` → `make -C pmoves secrets-funnel`. The funnel is the only supported path into CHIT storage.
- `*_FILE` secret support is wired across focus services via `pmoves/services/common/env.py::get_secret` — prefer the `_FILE` form for compose-injected secrets.

**The canonical secrets pipeline is `make -C pmoves secrets-funnel`.** It is defined in `pmoves/mk/codex.mk` — **not** in `pmoves/Makefile`. A grep of the root Makefile alone will not find it. Before adding any secrets tooling, run `grep -rn 'secrets-funnel' pmoves/Makefile pmoves/mk/` and `make -C pmoves help`. A duplicate funnel has been written twice by agents who checked only the root Makefile and concluded the target did not exist.

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

<!-- autoclaw:skill-path-guidance -->
## Installing Skills

When creating or installing a new skill, always place it in:

`~/.openclaw-autoclaw/skills/<skill-name>/SKILL.md`

This is the managed skills directory. The agent will automatically discover
any skill placed here — no extra configuration needed. Do NOT install skills
into `~/.agents/skills/` (that directory is shared with other tools).

<!-- /autoclaw:skill-path-guidance -->

<!-- autoclaw:browser-agent-guidance -->
## Browser Automation

For any task that requires a browser, **prefer `autoglm-browser-agent`**. Use it as the first choice.

- ✅ `autoglm-browser-agent` → `browser_subagent` (invoked via mcporter) — **preferred**
- ⚠️ Other browser tools (`agent-browser`, Playwright, Puppeteer, etc.) — fallback only when `autoglm-browser-agent` is unavailable or fails

Always try `autoglm-browser-agent` first. Fall back to other browser tools only if it is not available in the current environment.
<!-- /autoclaw:browser-agent-guidance -->

<!-- autoclaw:image-recognition-guidance -->
## Image Recognition

For any image recognition task, **prefer `autoglm-image-recognition`**. Use it as the first choice.

- ✅ `autoglm-image-recognition` — **preferred** for all image recognition tasks
- ⚠️ Built-in `image` tool or reading images directly with `read` — fallback only when `autoglm-image-recognition` is unavailable or fails

Do not use the built-in `image` tool or read an image and describe it yourself when `autoglm-image-recognition` is available.
<!-- /autoclaw:image-recognition-guidance -->

<!-- autoclaw:hermes-evolution-guidance -->
## Hermes-Evolution

**Current evolution intensity for this workspace/agent: aggressive (100%).**

The desktop app sends deterministic evolution-check messages (starting with `[SYSTEM: Post-turn evolution check`) after qualifying turns.
When you receive such a message, follow the `hermes-evolution` skill instructions to evaluate and potentially propose an evolution.
Apply the rules defined in the skill according to the **aggressive (100%)** intensity level.
This value is workspace-local. If asked about the current agent evolution intensity, report this value instead of the global gateway skill env.

Core principle: **never write to target files without user approval** — always use the draft/approve workflow.
User preference statements are not approval to directly edit MEMORY.md, AGENTS.md, TOOLS.md, USER.md, or managed SKILL.md files.
Use the evolution proposal card instead of editing target files directly; only apply changes after the user confirms the proposal.

### Evolution Echo
When you apply knowledge from a previously evolved rule (AGENTS.md, MEMORY.md, TOOLS.md, or a managed SKILL.md),
briefly mention it in your response: "（基于之前的经验：<one-line rule summary>）".
Keep it to one short line at most. Do not echo on every turn — only when an evolved rule directly influenced your approach.
<!-- /autoclaw:hermes-evolution-guidance -->

## Skills Constellation

POWERFULMOVES forks of upstream agent-skill repositories live under [`skills/`](skills/) — see [`skills/README.md`](skills/README.md) for the full map. All five forks landed across two singleton rounds on 2026-05-09 (z890): `Pmoves-skills` (Anthropic), `PMOVES-awesome-agent-skills`, `pmoves-fork-repository-skill`, `PMOVES-agent-sandbox-skill`, `Pmoves-claude-d3js-skill`. New external skill forks still require per-URL Bash-tool authorization (singleton add) — see `skills/README.md` for the procedure.


<!-- autoclaw:feishu-lark-skill-guidance -->
## Feishu / Lark Requests

When the user asks about Feishu/Lark/飞书 matters, route through Feishu/Lark skills first. This includes messaging, contacts, calendars, approvals, tasks, docs, sheets, Base, Drive, Wiki, mail, meetings, minutes, attendance, OKRs, or any other Feishu/Lark workspace operation.

1. If a relevant Feishu/Lark skill is already available, use that skill directly.
2. If no relevant skill is available, search the skill catalog/store or available skill list for a matching Feishu/Lark skill.
3. If you find a matching skill that is not installed or enabled, ask the user whether to install/enable and use it before proceeding.
4. If no matching skill exists, say so briefly and continue with the safest available fallback.
<!-- /autoclaw:feishu-lark-skill-guidance -->