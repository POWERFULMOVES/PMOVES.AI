# Agent Zero Context — Consolidated Brief

**Purpose:** Authoritative reference for all Agent Zero sessions on PMOVES.AI.
**Generated:** 2026-04-19 from 14 source documents + 23 agent learnings.
**Rule:** Read this BEFORE acting. If in doubt, check `.claude/context/services-catalog.md` — it is the single source of truth for ports.

---

## 1. CRITICAL CORRECTIONS

### Port Numbers

TensorZero uses **port 3000** for Docker-internal communication (confirmed in docker-compose.yml: `TENSORZERO_BASE_URL=http://tensorzero-gateway:3000`). CLAUDE.md references port 3030 for host-exposed access. Both are correct in their respective contexts. Grafana owns host port 3000.

| Service | Docker-Internal | Host-Exposed | Notes | Source |
|---------|-----------------|--------------|-------|--------|
| **TensorZero Gateway** | **3000** | **3030** | 3000 for containers, 3030 for host | docker-compose.yml, CLAUDE.md |
| **TensorZero UI Dashboard** | **4000** | — | Internal only, not host-exposed |
| **ClickHouse (TZ observability)** | **8123** | — | tensorzero.md |
| **Grafana** | **3000** | — | services-catalog.md |
| **Agent Zero** | **8080** (API), **8081** (UI) | — | services-catalog.md |
| **Archon** | **8091** (API), **3737** (UI), **8051/8052** (MCP) | — | services-catalog.md |
| **BoTZ MCP Gateway** | **2091** (internal) | 8054 (host-exposed) | docker-compose.yml maps 8054:8054; services-catalog.md lists 2091 as internal port |
| **Gateway Agent** | **8100** (internal) | — | services-catalog.md |
| **Model Registry** | **8111** | 8110 (changed PR #845) | services-catalog.md |
| **BoTZ VPN MCP** | **8110** | — | services-catalog.md (took 8110 after Model Registry moved) |
| **Cipher Memory API** | **8105** (remapped from 3000) | — | services-catalog.md |
| **Headscale** | **8096** (API), **9091** (metrics) | — | services-catalog.md |
| **Health (wger)** | **8000** (`WGER_PORT`) | 8080 (Agent Zero) | services-catalog.md |
| **Neo4j** | **7474** (HTTP), **7687** (Bolt) | — | services-catalog.md |
| **NATS** | **4222** (TCP), **9222** (WS standalone), **9223** (WS docked) | — | services-catalog.md |
| **Supabase** | **3010** (PostgREST), **5432** (Postgres) | — | services-catalog.md |
| **Prometheus** | **9090** | — | services-catalog.md |
| **Loki** | **3100** | — | services-catalog.md |
| **MinIO** | **9000** (API), **9001** (Console) | — | services-catalog.md |
| **Qdrant** | **6333** | — | services-catalog.md |
| **Meilisearch** | **7700** | — | services-catalog.md |
| **Hi-RAG v2** | **8086** (CPU), **8087** (GPU) | 8089 (that's v1/legacy) | services-catalog.md |
| **Hi-RAG v1** | **8089** (CPU), **8187** (GPU) | — | services-catalog.md (LEGACY) |
| **Flute-Gateway** | **8055** (HTTP), **8056** (WS) | — | services-catalog.md |
| **Ultimate-TTS-Studio** | **7861** | — | services-catalog.md |
| **Voice Relay** | **8121** | — | services-catalog.md |
| **PMOVES.YT** | **8077** | — | services-catalog.md |
| **FFmpeg-Whisper** | **8078** | — | services-catalog.md |
| **Extract Worker** | **8083** | — | services-catalog.md |
| **SupaSerch** | **8099** | — | services-catalog.md |
| **DeepResearch** | **8098** | — | services-catalog.md |
| **GPU Orchestrator** | **8200** | — | services-catalog.md |
| **Evo Controller** | **8113** | — | services-catalog.md |
| **Tokenism Simulator** | **8103** (host) → **8100** (internal) | — | services-catalog.md |
| **A2UI NATS Bridge** | **9224** | — | services-catalog.md |
| **RustDesk** | **21115-21119** | — | services-catalog.md |
| **Open Notebook** | **8503** (UI), **5055** (API) | — | services-catalog.md |

### Port Conflict Notes

- **Headscale (8096) and Cipher Memory (8105)** use different port numbers. Cipher Memory was reassigned from 8096 to 8105 in PR #1344/#1345 to eliminate the collision.
- ~~"Cipher Memory" and "Headscale" both appear at 8096~~ → **Resolved** — Cipher Memory moved to 8105, Headscale retains 8096.
- **Tokenism (8103→8100 internal) and Gateway Agent (8100 internal)** share internal port 8100 but use different host mappings.
- **cAdvisor defaults to 8080** which conflicts with Agent Zero — must be reconfigured.

### Service Name Corrections

- "BoTZ MCP Gateway" has two ports: **2091** (internal, per services-catalog.md) and **8054** (host-exposed, per docker-compose.yml `8054:8054` mapping). Both are active. The 2091 is the container-internal port; 8054 is the host binding.
- "Gateway Agent" at 8100 is a separate service from "BoTZ MCP Gateway" at 2091.
- ~~"Cipher Memory" and "Headscale" both appeared at 8096~~ → **Resolved** in PR #1344/#1345. Cipher Memory is now at 8105.

### Environment Variable Naming

- `SUPABASE_JWT_SECRET` = `JWT_SECRET` (legacy alias). All services use `SUPABASE_JWT_SECRET`.
- `CHIT_PASSPHRASE` — required in production, fail-closed if missing. Sidecar dev mode uses `dev-local-sidecar-override`.
- `CHIT_SIGNING_KEY` / `CHIT_ENCRYPTION_KEY` — separate keys for separate crypto purposes. Fall back to `CHIT_PASSPHRASE` with warning.
- `AGENTZERO_JETSTREAM=true` — required for NATS reliable delivery. False in standalone sidecar mode.
- `TOPOLOGY_MODE` — `standalone` (sidecar) or `docked` (compose stack).
- NATS auth: always `nats://nats:pmoves@nats:4222` (authenticated, not `nats://nats:4222`).

---

## 2. ESTABLISHED CONVENTIONS

### Test Structure & Location

| Directory | Purpose | Runner | Parallel |
|-----------|---------|--------|----------|
| `pmoves/tests/unit/` | Pure unit tests (mock-only, no Docker/network) | `pytest` | Yes (`-n auto`) |
| `pmoves/tests/smoke/` | Quick health checks (5-30s), service endpoints | `pytest -n auto` | Yes |
| `pmoves/tests/integration/` | Multi-service integration tests | `pytest` (sequential) | No |
| `pmoves/tests/functional/` | End-to-end feature tests | `pytest` | No |
| `pmoves/tests/services/` | Per-service test suites | `pytest` | Varies |
| `pmoves/tests/hardening/` | Security hardening verification | `pytest` | No |
| `pmoves/tests/a2ui/` | A2UI-specific tests | `pytest` | No |

**Critical rule from PR #1287 review:** Pure unit tests using only `unittest.mock` MUST go in `tests/unit/`, NOT `tests/smoke/`. Smoke tests run with `-n auto` and are defined as "Quick health checks for validating service endpoints."

**Test quality standards (from PR #1287):**
- Use `patch.object(instance, ...)` not `patch.object(Path, ...)` for class methods — prevents parallel flaking
- Extract repeated dict literals into factory functions
- Use `@pytest.mark.parametrize` for symmetric test pairs
- Remove unused fixtures (e.g., `capsys` if never calling `readouterr()`)
- Even stubs deserve tests — they encode contracts (function signatures, error messages, subject names)

### PR Creation & Review Process

1. Create feature branch from `main`
2. Write code + tests (tests required for ALL changes, even stubs)
3. Run `make -C pmoves env-check` and relevant test suites locally
4. Push and open PR against `main`
5. Agent Zero `code-reviewer` subordinate reviews (or `pr-trimmer` Claude agent)
6. Address all Critical and Important issues
7. CI must pass before merge

**PR review structure (from reviews/):**
- Verdict: APPROVE / REQUEST CHANGES / MERGE WITH FIX
- Issues classified: Critical / Important (blocks merge) / Suggestion (optional)
- Verification story: tests reviewed, build verified, security checked, cross-references verified
- Required Before Merge table with severity

### Commit Message Format

Conventional commits: `type(scope): description`

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `security`, `ci`

Scopes match service/subsystem names: `services`, `chit`, `nats`, `tensorzero`, `agent-zero`, `port_audit`, etc.

### Branch Naming

- `feat/<short-description>` — features
- `fix/<short-description>` — bug fixes
- `test/<short-description>` — test additions
- `security/<short-description>` — security fixes

### File Naming

- Python: `snake_case.py`
- YAML configs: `snake_case.yaml` or `kebab-case.yaml` (be consistent within a directory)
- TAC trees: `name.tac.yaml` (e.g., `dgx-spark.tac.yaml`)
- NATS stream configs: `descriptive_name.yaml` (e.g., `mesh_gpu_streams.yaml`)
- Agent definitions: `name.md` in `.claude/agents/`

### Import Patterns

- Shared types go in `pmoves/services/common/` (e.g., `nats_types.py` for `SubjectEntry`)
- CHIT crypto: import from `pmoves.tools.chit_security` and `pmoves.tools.chit_common` — do NOT define local `canon()` or `verify_hmac()`
- Service stubs: docstring-only `__init__.py` — NEVER `raise NotImplementedError` at module level

### TAC Tree Schema

**Canonical schema** (26 trees use this): `name:` + `root:` with nested `children:`.

```yaml
name: my-tac-tree
root:
  name: Phase 1
  children:
    - name: Step 1.1
      expect: "..."
```

**FORBIDDEN schema** (cataclysm-studios attempted this): `tac_tree:` with `phases:` list. This was rejected in PR #1279 review and rewritten to canonical form.

### NATS Subject Conventions

- All lowercase (e.g., `discord.messages.fetched.v1`, not `Discord.messages.fetched.v1`)
- Versioned: always `v1` suffix
- Hierarchical: `domain.subdomain.action.v1`
- Domain prefixes: `mesh.`, `ingest.`, `research.`, `geometry.`, `botz.`, `evoswarm.`, `health.`, `finance.`, `agent.`, `voice.`, `fleet.`, `crush.`, `shape.`, `skills.`
- JetStream stream wildcards must actually cover the subjects published (see PR #1279 C2)
- `max_bytes` must be integer (e.g., `268435456`), NOT human-readable (`256MB`)

---

## 3. CI/CHECKS REQUIREMENTS

### CI Pipelines

| Pipeline | Trigger | Arch | Security | When Used |
|----------|---------|------|----------|-----------|
| `integrations-ghcr` | push to main/pr | multi-arch (amd64+arm64) | Trivy scan + Cosign + SBOM | Major services (Agent Zero, Archon, SupaSerch, PMOVES.YT, Health, A2UI) |
| `self-hosted-builds` | push to main/pr | amd64 only | Cosign | Services that need GPU or local deps (FFmpeg-Whisper, Extract Worker, Publisher-Discord) |
| `build-images` | manual dispatch (`workflow_dispatch`) | amd64 | None | Custom builds, new services, GPU-heavy images (TTS, GPU Orchestrator) |
| `vendor` | N/A | N/A | N/A | Upstream images used directly (NATS, Supabase, Qdrant, Neo4j, Meilisearch, MinIO, Prometheus, Grafana, Loki, Headscale, RustDesk) |
| `local-build-only` | N/A | N/A | N/A | Built via compose `build:` directive only (Media-Video, Media-Audio, LangExtract, Notebook Sync, Presign, Render Webhook, Jellyfin Bridge, Cipher Memory) |
| `sync-secrets-local` | manual dispatch | N/A | N/A | GitHub Secrets → CHIT bundle sync |

### Required Checks Before Merge

1. **All triggered CI pipelines pass** (integrations-ghcr and/or self-hosted-builds)
2. **Tests pass** — relevant test suite for the changed code
3. **No Trivy critical/high vulnerabilities** (for integrations-ghcr jobs)
4. **Cosign signature verification passes**
5. **PR review approved** — all Critical and Important issues resolved
6. **`git diff --stat`** shows only intended files

### Local Pre-push Validation

```bash
make -C pmoves env-check          # Environment preflight
make -C pmoves auth-alignment     # Cross-tier credential consistency
pytest pmoves/tests/unit/         # Unit tests
pytest pmoves/tests/smoke/        # Smoke tests
# For YAML: python3 -c "import yaml; yaml.safe_load(open('file'))"
# For TOML: python3 -c "import tomllib; tomllib.load(open('file','rb'))"
# For SQL: psql -c "BEGIN; \i file.sql; ROLLBACK;"
```

### Branch Protection

- `main` branch is protected
- CI must pass before merge
- PR reviews required
- Force push disabled

---

## 4. AGENT RESPONSIBILITIES & BOUNDARIES

### The Three-Body Solution (Claude Code)

Defined in `.claude/agents/` with tool-level enforcement:

| Agent | Body | Can Edit? | Disallowed Tools | Key Constraint |
|-------|------|-----------|-----------------|----------------|
| `delivery-agent` | Delivery | **Yes** | `EnterPlanMode` | Executes approved work, never plans |
| `control-agent` | Control | **No** | `Write`, `Edit`, `EnterPlanMode` | Read-only observer, no modifications |
| `memory-agent` | Memory | **No** | All except cipher/CHIT skills | Cipher/CHIT operations only |
| `researcher` | — | **No** | Sub-agents | Read-only, no delegation |
| `test-runner` | — | **No** | All except pytest | Worktree-isolated, pytest only |
| `pr-trimmer` | — | **Yes** | `EnterPlanMode` | Worktree-isolated, PR review specialist |

### Agent Lanes (who works where)

| Agent | Primary Node | Lane |
|-------|-------------|------|
| Z890-CLAUDE | z890 | Infra, fleet, compose, CI runners |
| 4090-CLAUDE | 4090 laptop | Provider cascade, Shift Crew, field testing |
| 5090-CLAUDE | 5090 | GPU, voice stack, submodule sync |
| CODEX-GPT5 | any | Docs, prospectus, creator control plane |
| KILOCODE-GLM | 5090 | GLM coding plan, vLLM, Proxmox |
| PMOVES-MINIMAX | any | Token plan overflow, writing, hyperdimensions |
| CLAUDE-OPUS | any | Architecture, self-review, convergence |

### Agent Zero (this agent) Responsibilities

- **Sidecar mode**: Standalone agent interface for deploying PMOVES.AI on new systems
- **Uses `code_execution_remote`** for host access (not direct Docker)
- **Uses Mini CLI** for orchestration: `python3 -m pmoves.tools.mini_cli <command>`
- **Delegates** to subordinates: researcher, code-reviewer, test-engineer, security-auditor, developer, skill-creator
- **Does NOT** directly edit Claude Code agent definitions (`.claude/agents/`)
- **Does NOT** modify compose files or service Dockerfiles directly — delegates to developer

### Overlap Zones & Conflict Prevention

1. **Port changes**: If any agent changes a port, it MUST update: (a) `services-catalog.md`, (b) `docker-compose*.yml`, (c) `env.*` files, (d) any cross-reference in TAC trees or agent docs. This was the root cause of PR #845 (Model Registry 8110→8111).
2. **NATS subjects**: New subjects MUST be added to `nats-subjects.md` AND the relevant `nats_subject_registry.py` AND JetStream stream configs. PR #1279 demonstrated what happens when streams don't cover subjects.
3. **CHIT crypto**: All crypto MUST delegate to `chit_security.py` / `chit_common.py`. No local `canon()` or `verify_hmac()` copies. PR #1275 established this after finding divergent implementations.
4. **Cross-node context**: Claude's context is NOT consistent across z890/4090/5090. Always verify before assuming. Run health checks and check claim register.

---

## 5. FORBIDDEN ACTIONS

### Hard Rules (learned from reviews and learnings)

1. **NEVER merge a PR without CI passing.** No exceptions.

2. **NEVER use `raise NotImplementedError` at module level in `__init__.py`.** This crashes `pytest --collect-only`, IDE tooling, and linters. Use docstring-only modules for stubs. (PR #1279 I3)

3. **NEVER duplicate `SubjectEntry` dataclass.** Extract to `pmoves/services/common/nats_types.py`. (PR #1279 I4)

4. **NEVER use TAC tree schema `tac_tree:/phases:`.** Always use `name:/root:/children:`. (PR #1279 I2)

5. **NEVER use `max_bytes: 256MB` in JetStream configs.** Must be integer bytes. (PR #1279 C1)

6. **NEVER define local `canon()` or `verify_hmac()` for CHIT.** Import from `chit_common` / `chit_security`. (PR #1275 M1)

7. **NEVER use hardcoded credential fallbacks (`"change-me"`, `changeme`, `minioadmin`).** Fail-closed with `RuntimeError`. (PR #1275 H1)

8. **NEVER patch class methods globally in tests.** Use instance patches to avoid parallel flaking. (PR #1287)

9. **NEVER put pure unit tests in `tests/smoke/`.** Use `tests/unit/`. (PR #1287)

10. **NEVER use uppercase in NATS subject names.** All lowercase. (PR #1279 S1)

11. **NEVER change a service port without updating ALL references:** services-catalog.md, docker-compose files, env files, TAC trees, agent topology docs, nats-subjects.md.

12. **NEVER add new TensorZero function variants at non-zero weight.** Always `weight = 0.0` for safe rollout. (MODEL_ONBOARDING.md)

13. **NEVER publish to NATS subjects not declared in your agent's registry.** Cross-cutting events flow through the orchestrator (Agent Zero). (AGENT_CLASS_TAXONOMY.md — Invocation Discipline)

14. **NEVER make transitive agent calls.** Agent A cannot call Agent B which silently calls Agent C. All call chains must be visible and auditable. (AGENT_CLASS_TAXONOMY.md — Invocation Discipline)

15. **NEVER add non-commercial licensed models to production.** Only Apache 2.0 / MIT / Gemma / BSD. (MODEL_ONBOARDING.md)

### Soft Rules (strongly discouraged)

- Don't stack 4+ distinct concerns in a single PR — split into smaller, reviewable PRs. (PR #1279 S6)
- Don't add unused imports (`logger`, `json`) — remove them. (PR #1279 S3-S4)
- Don't let docstring counts drift from assert guards (e.g., "88 subjects" when assert says 97). (PR #1279 S2)
- Don't mix wildcard NATS subjects with concrete entries without comments. (PR #1279 S5)
- Don't write inline cross-reference paths without verifying they exist. (PR #1279 S8-S9)

---

## 6. KEY FILE MAP

### Authoritative Configuration (single source of truth)

| File | Purpose | Who Owns |
|------|---------|----------|
| `pmoves/config/agent_registry.yaml` | Machine-readable agent registry (class, type, ports, NATS, CHIT) | Claude Code (delivery) |
| `.claude/context/services-catalog.md` | Human-readable service port/API/CI reference | Claude Code (delivery) |
| `.claude/context/nats-subjects.md` | NATS subject catalog (80+ subjects) | Claude Code (delivery) |
| `.claude/context/tensorzero.md` | TensorZero gateway config reference | Claude Code (delivery) |
| `.claude/context/credentials-workflow.md` | Secrets bootstrap/rotation workflow | Claude Code (delivery) |
| `pmoves/config/gpu-models.yaml` | GPU VRAM catalog | Claude Code (delivery) |
| `pmoves/configs/flare-model-namespace.yaml` | Operator-facing model aliases | Claude Code (delivery) |
| `pmoves/tensorzero/config/tensorzero.toml` | TensorZero routing config | Claude Code (delivery) |
| `pmoves/supabase/initdb/12_model_registry_seed.sql` | Supabase model seed data | Claude Code (delivery) |
| `pmoves/config/provider_catalog.yaml` | LLM provider definitions | Claude Code (delivery) |
| `pmoves/chit/secrets_manifest.yaml` | Canonical variable definitions for secrets | Claude Code (delivery) |

### Agent Definitions & Coordination

| File | Purpose | Who Owns |
|------|---------|----------|
| `.claude/agents/delivery-agent.md` | Delivery body agent (can edit) | Claude Code architecture |
| `.claude/agents/control-agent.md` | Control body agent (read-only) | Claude Code architecture |
| `.claude/agents/memory-agent.md` | Memory body agent (CHIT only) | Claude Code architecture |
| `.claude/agents/researcher.md` | Read-only researcher | Claude Code architecture |
| `.claude/agents/test-runner.md` | Worktree-isolated pytest runner | Claude Code architecture |
| `.claude/agents/pr-trimmer.md` | Worktree-isolated PR reviewer | Claude Code architecture |
| `AGENTS.md` | Project-wide multi-agent conventions | All agents |
| `docs/AGENTS/AGNOTE4482_SITREP.md` | Cold-start orientation for any agent | All agents |
| `docs/AGENTS/AGNOTE4482PHI.t1.md` | Active claim register | All agents |
| `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` | Agent type system (60 agents) | Claude Code architecture |
| `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` | Visual topology + TAC tree | Claude Code architecture |

### Crypto & Security

| File | Purpose | Who Owns |
|------|---------|----------|
| `pmoves/tools/chit_security.py` | Canonical CHIT crypto (PBKDF2, AES-GCM, HMAC) | Claude Code (security) |
| `pmoves/tools/chit_common.py` | Canonical `canon()` serialization | Claude Code (security) |
| `pmoves/tools/chit_security_validator.py` | Fail-closed CHIT signature validator | Claude Code (security) |
| `pmoves/services/common/nats_types.py` | Shared `SubjectEntry` dataclass | Claude Code (delivery) |

### Credentials & Environment

| File | Purpose | Who Owns |
|------|---------|----------|
| `pmoves/env.shared` | Single source of truth for env vars (gitignored) | Claude Code (infra) |
| `pmoves/env.tier-*` | Per-tier env subsets (auto-populated) | Auto-generated |
| `~/.config/pmoves/chit/env.cgp.json` | CHIT bundle (hex-encoded secrets) | `sync-secrets-local` workflow |
| `pmoves/scripts/supabase/generate-keys.sh` | JWT/DB key generation | Claude Code (infra) |
| `pmoves/tools/brand_defaults.py` | Seeded credential defaults | Claude Code (infra) |

### Testing

| File | Purpose | Who Owns |
|------|---------|----------|
| `pmoves/tests/unit/` | Pure unit tests | Agent Zero (test-engineer) |
| `pmoves/tests/smoke/` | Quick health checks | Agent Zero (test-engineer) |
| `pmoves/tests/test_chit_security.py` | CHIT crypto tests (664 lines) | Claude Code (security) |
| `pmoves/tests/unit/test_port_audit.py` | Port audit tests (61 tests) | Agent Zero (test-engineer) |

### Operations

| File | Purpose | Who Owns |
|------|---------|----------|
| `pmoves/docs/operations/MODEL_ONBOARDING.md` | Model registry update runbook | Claude Code (delivery) |
| `pmoves/tools/agent_taxonomy_helper.py` | Agent registry CLI query tool | Claude Code (delivery) |
| `pmoves/tools/port_audit.py` | Port conflict detection | Claude Code (infra) |
| `pmoves/tools/mini_cli.py` | Sidecar orchestration CLI | Agent Zero |

---

### Cipher Memory MCP Gap (3-layer, documented 2026-04-01)

- **Layer 1 (skills):** Fixed — skills use MCP-first with local MEMORY.md fallback
- **Layer 2 (MCP client):** `pmoves-cipher-mcp/cipher_mcp/client.py` calls `POST /api/memory` and `GET /api/memory/search` — endpoints that don't exist yet
- **Layer 3 (cipher-api):** `Pmoves-cipher/src/app/api/server.ts` registers `/api/message`, `/api/sessions`, `/api/mcp` but NO `/api/memory` routes
- **Working path:** Local MEMORY.md only. Skills auto-fallback when MCP call fails.
- **Fix needed:** Implement `/api/memory` CRUD routes in `Pmoves-cipher` submodule (separate PR)

### CHIT Crypto Migration (from PR #1275 audit)

- **P1 follow-up:** Gateway `chit.py` still has local `canon()` and `verify_hmac()` — needs migration to `chit_security`/`chit_common`
- **P1 follow-up:** `sync_common_credentials()` insecure defaults still reachable via fallback path
- **P2 follow-up:** `geometry_decoder.py` still uses scrypt (not yet migrated to PBKDF2)
- **P2 follow-up:** `helpers/crypto.py` may or may not be related to CHIT — needs evaluation

### Model Onboarding (from MODEL_ONBOARDING.md)

- PR #1226 in progress: Gemma 4 family (E2B/E4B/26B-A4B/31B) onboarding
- Introduces new `multimodal_large` TensorZero function for larger models

### Cross-Node Context Gap

- Claude context is NOT consistent across z890/4090/5090
- Each node may have different containers, worktrees, claim register state
- Always verify with health checks before assuming

### Changelog

- **2026-04-19**: CI audit — 9 PRs merged (#1290-#1299), merge-gate passing, `claude-review` flake on #1290-1293 (known, non-blocking). No regressions.

---

## Appendix A: Agent Class Quick Reference

| Class | Prefix | Example | Analogy |
|-------|--------|---------|---------|
| Legendary | `POWERFULMOVES` | `POWERFULMOVES/PMOVES.AI` | Arceus / Primus |
| Standard | `PMOVES-` | `PMOVES-Agent-Zero`, `PMOVES-Archon` | Charizard / Autobot |
| Specialized | `Pmoves-` | `Pmoves-cipher`, `Pmoves-hyperdimensions` | Regional variant / Combiner |
| Utility | `pmoves-` | `pmoves-surf`, `pmoves/tools/*` | Item/Ability / Minicon |

## Appendix B: Agent Type Quick Reference

| Type | Tier | Element | Key Agents |
|------|------|---------|------------|
| Data | 1 | Earth | Supabase, Qdrant, Neo4j, Meilisearch, NATS, Cipher |
| API | 2 | Water | TensorZero, Flute-Gateway, Presign |
| LLM | 3 | Fire | DeepResearch, TensorZero (secondary) |
| Worker | 4 | Electric | Hi-RAG, Extract Worker, GPU Orchestrator |
| Media | 5 | Wind | PMOVES.YT, FFmpeg-Whisper, TTS services |
| Agent | 6 | Psychic | Agent Zero, Archon, SupaSerch, BoTZ |
| UI | 7 | Light | MAI-UI, Grafana, A2UI, Hyperdimensions |

## Appendix C: Credential Source Priority

```
1. CHIT bundle (~/.config/pmoves/chit/env.cgp.json)     ← decoded by secrets-funnel-sync
2. env.shared (pmoves/env.shared)                        ← gitignored, single source of truth
3. env.tier-* (auto-populated from env.shared)            ← per-tier subsets
4. .env.local (machine-local overrides)                   ← gitignored
5. GitHub Secrets (CI-only, push via push-gh-secrets.sh)  ← cloud
6. CHIT manifest (pmoves/chit/secrets_manifest.yaml)      ← canonical variable definitions
7. bootstrap/registry.json                                ← declarative generation rules
```

## Appendix D: Sidecar Mode Env Defaults

| Variable | Sidecar (Standalone) | Docked (Compose) |
|----------|---------------------|------------------|
| `TOPOLOGY_MODE` | `standalone` | `docked` |
| `CHIT_REQUIRE_SIGNATURE` | `false` | `true` |
| `CHIT_DECRYPT_ANCHORS` | `false` | `true` |
| `CHIT_PASSPHRASE` | `dev-local-sidecar-override` | From CHIT bundle |
| `AGENTZERO_JETSTREAM` | `false` | `true` |
| Ollama | `host.docker.internal:11434` | Compose service |

---

*This brief is derived from: `.claude/CLAUDE.md`, `LEARNINGS.md`, `AGENTS.md`, `.claude/agents/*` (6 files), `.claude/learnings/*` (23 files), `.claude/context/nats-subjects.md`, `.claude/context/tensorzero.md`, `.claude/context/services-catalog.md`, `.claude/context/credentials-workflow.md`, `reviews/*` (3 files), `docs/AGENTS/AGNOTE4482_SITREP.md`, `docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md`, `docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md`, `docs/operations/MODEL_ONBOARDING.md`.*
