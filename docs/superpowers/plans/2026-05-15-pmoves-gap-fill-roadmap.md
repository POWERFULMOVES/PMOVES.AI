# PMOVES.AI Gap-Fill Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 35 automation gaps identified by parallel governance/skills/Archon/MCP-ecosystem audits, prioritized for the Archon-as-mint trajectory.

**Architecture:** Three execution waves. Wave 0 (this session, autonomous): scaffold composable skills, subagent definitions, hook scripts, slash commands, and the NATS MCP server skeleton — all file-only changes inside `.claude/` and a new `pmoves-nats-mcp/` project. Wave 1 (operator-gated): live MCP installs needing API tokens; Supabase schema migrations. Wave 2 (service-side): NATS mint subjects published by Archon services, three-body quorum MCP.

**Tech Stack:** Python (uv, nats-py, mcp library), Bash hooks, Markdown skill/agent/command definitions, NATS JetStream, existing `.claude/hooks/damage-control/` pattern.

---

## Wave 0 — Autonomous scaffolding (this session)

### Task 1: Initialize `skills/` constellation submodules

**Files:**
- Modify (git index): `skills/Pmoves-skills`, `skills/PMOVES-awesome-agent-skills`, `skills/pmoves-fork-repository-skill`, `skills/PMOVES-agent-sandbox-skill`, `skills/Pmoves-claude-d3js-skill`
- Create: `.claude/skills/fork-repository/SKILL.md` (pointer)
- Create: `.claude/skills/agent-sandbox/SKILL.md` (pointer)
- Create: `.claude/skills/claude-d3js/SKILL.md` (pointer)

- [ ] **Step 1:** Run `git submodule update --init skills/` to check out the 5 forks.
- [ ] **Step 2:** Create `.claude/skills/fork-repository/SKILL.md` that points to the activated submodule with frontmatter `name: fork-repository`, `description: Fork the running agent N times to branch engineering work`.
- [ ] **Step 3:** Repeat for `agent-sandbox/SKILL.md` and `claude-d3js/SKILL.md`.
- [ ] **Step 4:** Update `skills/README.md` Status column to reflect ✅ activated.
- [ ] **Step 5:** Commit: `feat(skills): activate fork-repository / agent-sandbox / claude-d3js constellation`.

### Task 2: Author `pmoves-mesh-preflight` skill

**Files:**
- Create: `.claude/skills/pmoves-mesh-preflight/SKILL.md`
- Create: `.claude/skills/pmoves-mesh-preflight/scripts/preflight.sh`

- [ ] **Step 1:** Write SKILL.md frontmatter: `name: pmoves-mesh-preflight`, `description: Run /healthz across all services in .claude/CATALOG.md and emit pass/fail snapshot. Use before claiming work in AGNOTE4482PHI.t1.md.`
- [ ] **Step 2:** Write `preflight.sh` that parses `.claude/CATALOG.md`, hits each `/healthz`, prints a table, exits non-zero on any failure.
- [ ] **Step 3:** Smoke-test against a known service (cipher :8105).
- [ ] **Step 4:** Commit: `feat(skill): add pmoves-mesh-preflight for catalog-driven health checks`.

### Task 3: Author `pmoves-nats-subject-audit` skill

**Files:**
- Create: `.claude/skills/pmoves-nats-subject-audit/SKILL.md`
- Create: `.claude/skills/pmoves-nats-subject-audit/scripts/audit.py`

- [ ] **Step 1:** Write SKILL.md (Claude-only via `user-invocable: false`).
- [ ] **Step 2:** Write `audit.py` — reads `.claude/context/nats-subjects.md` + `geometry-nats-subjects.md`, queries NATS server `/jsz?streams=true` endpoint at `:8222`, diffs declared vs live, returns orphan list.
- [ ] **Step 3:** Commit: `feat(skill): add pmoves-nats-subject-audit`.

### Task 4: Author `pmoves-living-docs-refresh` skill

**Files:**
- Create: `.claude/skills/pmoves-living-docs-refresh/SKILL.md`
- Create: `.claude/skills/pmoves-living-docs-refresh/scripts/refresh.sh`

- [ ] **Step 1:** Write SKILL.md.
- [ ] **Step 2:** `refresh.sh` wraps `make -C pmoves docs-reconcile-check` then for each stale entry, emits an instruction block to regenerate from its registered source.
- [ ] **Step 3:** Commit: `feat(skill): add pmoves-living-docs-refresh`.

### Task 5: Author `pmoves-submodule-fleet` skill

**Files:**
- Create: `.claude/skills/pmoves-submodule-fleet/SKILL.md`
- Create: `.claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh`

- [ ] **Step 1:** Write SKILL.md.
- [ ] **Step 2:** `fleet_audit.sh` runs `git submodule status --recursive`, detects detached HEADs, computes commits-behind-main per submodule, prints batch promotion proposal.
- [ ] **Step 3:** Commit: `feat(skill): add pmoves-submodule-fleet`.

### Task 6: Author `pmoves-chit-sign` skill

**Files:**
- Create: `.claude/skills/pmoves-chit-sign/SKILL.md`

- [ ] **Step 1:** Write SKILL.md that wraps existing `/chit:sign-trail` slash command + appends to `AGNOTE4482PHI.t1.md` + publishes `chit.signed.v1` (via NATS MCP once available).
- [ ] **Step 2:** Commit: `feat(skill): add pmoves-chit-sign for composable trail signing`.

### Task 7: Subagent definitions (5 agents)

**Files:**
- Create: `.claude/agents/nats-subject-auditor.md`
- Create: `.claude/agents/chit-compliance-reviewer.md`
- Create: `.claude/agents/claim-collision-agent.md`
- Create: `.claude/agents/chit-pr-audit-agent.md`
- Create: `.claude/agents/archon-qa-agent.md`

- [ ] **Step 1:** Write each `.md` with frontmatter (`name`, `description`, `tools`) + body explaining trigger conditions, output format, and citation paths.
- [ ] **Step 2:** Smoke-test by referencing one agent in a follow-up subagent dispatch.
- [ ] **Step 3:** Commit: `feat(agents): add 5 governance/Archon subagents`.

### Task 8: Hook scripts (4 hooks)

**Files:**
- Create: `.claude/hooks/governance/signoff-gate.sh`
- Create: `.claude/hooks/governance/known-roads-enforcer.py`
- Create: `.claude/hooks/governance/claim-collision-pre.py`
- Modify: `.claude/hooks/session-env-check.sh` (append humility disclosure block)

- [ ] **Step 1:** Write `signoff-gate.sh` — reads stdin (PreToolUse Bash payload), if command matches `gh pr merge`, parses PR number, greps `pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md` (or PR description) for `[ACK: delivery]`, `[ACK: control]`, `[ACK: memory]` — exits 2 with stderr if any missing.
- [ ] **Step 2:** Write `known-roads-enforcer.py` — PreToolUse Bash hook; if command matches `docker compose up|restart` and is NOT inside an allowed `make` invocation, exits 2 with a hint to the equivalent `make -C pmoves up-*` target.
- [ ] **Step 3:** Write `claim-collision-pre.py` — PreToolUse Edit/Write hook on `AGNOTE4482PHI.t1.md`; scans existing CLAIM entries without RELEASE for the same branch name, exits 2 on collision.
- [ ] **Step 4:** Append humility disclosure block to `session-env-check.sh`.
- [ ] **Step 5:** Add a `# OPTIONAL — operator must enable in .claude/settings.json` note to each new hook. Do NOT auto-wire into settings.json (operator decision).
- [ ] **Step 6:** Commit: `feat(hooks): add governance hooks (signoff-gate, known-roads, claim-collision, humility)`.

### Task 9: Archon mint slash commands

**Files:**
- Create: `.claude/commands/archon/mint-agent.md`
- Create: `.claude/commands/archon/mint-skill.md`
- Create: `.claude/commands/archon/creator-onboard.md`

- [ ] **Step 1:** Write each command with frontmatter and a body describing the flow (scaffold → QA → register → publish NATS).
- [ ] **Step 2:** Reference the not-yet-built `archon:create-agent` MCP tool and document the contract.
- [ ] **Step 3:** Commit: `feat(commands): add /archon:mint-agent, /archon:mint-skill, /archon:creator-onboard`.

### Task 10: NATS MCP server skeleton

**Files:**
- Create: `pmoves-nats-mcp/pyproject.toml`
- Create: `pmoves-nats-mcp/src/nats_mcp/__init__.py`
- Create: `pmoves-nats-mcp/src/nats_mcp/server.py`
- Create: `pmoves-nats-mcp/README.md`
- Modify: `.claude/mcp.json` (add `pmoves-nats` server entry, **commented-out** until smoke-tested)

- [ ] **Step 1:** Create project structure modeled on `pmoves-cipher-mcp/`.
- [ ] **Step 2:** Write `server.py` exposing two MCP tools:
  - `nats_publish(subject: str, payload: str)` — connect with `NATS_URL` env, publish, return `{ "published": true, "subject": ... }`
  - `nats_subscribe(subject: str, timeout_seconds: int)` — connect, subscribe with timeout, return up to N captured messages
- [ ] **Step 3:** Add `.gitignore` for the new project.
- [ ] **Step 4:** Add `.claude/mcp.json` entry **commented in the README** (operator copies it in after `uv sync`).
- [ ] **Step 5:** Smoke test: publish to `test.gapfill.v1` via the MCP server CLI mode, observe with `nats sub`.
- [ ] **Step 6:** Commit: `feat(mcp): add pmoves-nats-mcp server (publish/subscribe)`.

### Task 11: PostToolUse format/lint hook (Tier 4 high-leverage)

**Files:**
- Create: `.claude/hooks/posttool-format/python-format.sh`
- Create: `.claude/hooks/posttool-format/ui-lint.sh`
- Note in `.claude/PATTERNS.md`: operator wires into `settings.json` when ready.

- [ ] **Step 1:** Write `python-format.sh` — runs `uv run ruff format` + `uv run ruff check --fix` on the changed file if path matches `*.py`.
- [ ] **Step 2:** Write `ui-lint.sh` — for paths under `pmoves/ui/`, runs `pnpm --silent --prefix pmoves/ui lint --fix --` on the changed file, then `pnpm --silent --prefix pmoves/ui typecheck`.
- [ ] **Step 3:** Document opt-in wiring in `.claude/PATTERNS.md`.
- [ ] **Step 4:** Commit: `feat(hooks): add opt-in PostToolUse format/lint scripts`.

### Task 12: Cross-link gap-fill artifacts in `.claude/PATTERNS.md`

**Files:**
- Modify: `.claude/PATTERNS.md` (append "Gap-fill artifacts (2026-05-15)" section)

- [ ] **Step 1:** Add a section listing each new skill / subagent / hook / command + activation path.
- [ ] **Step 2:** Commit: `docs(patterns): record gap-fill artifacts from 2026-05-15 roadmap`.

---

## Wave 1 — Operator-gated (user action required)

These need API tokens or remote resources; surface as PRs/instructions, do not auto-execute.

| # | Item | Why operator-gated |
|---|------|-------------------|
| W1.1 | Install Prometheus MCP | Needs `PROMETHEUS_URL` confirmation |
| W1.2 | Install Loki MCP | Same |
| W1.3 | Install Sentry MCP | Needs `SENTRY_AUTH_TOKEN`, `SENTRY_ORG` |
| W1.4 | Install Linear MCP | Needs `LINEAR_API_KEY` |
| W1.5 | Install Brave Search MCP | Needs `BRAVE_API_KEY` |
| W1.6 | Install Cloudflare MCP | Needs `CLOUDFLARE_API_TOKEN` |
| W1.7 | Install Playwright MCP | Browser binary install (`npx playwright install`) |
| W1.8 | Install Postgres MCP | Needs DB password from secrets-funnel |
| W1.9 | Install Fetch + Sequential-Thinking MCP | Local, no auth — operator opt-in |
| W1.10 | Supabase schema: `archon_minted_artifacts` table | DB migration |
| W1.11 | Supabase schema: `agent_id` FK on `archon_prompts` | DB migration |
| W1.12 | Enable Wave-0 hooks in `.claude/settings.json` | Operator decision |

> **Self-hosted note (2026-05-15)**: PMOVES.AI is self-hosted on ai-lab + Hostinger VPS with branded `pmoves.ai` DNS. Several Wave-1 SaaS MCPs above have self-hosted equivalents that should be preferred. See **Wave 1.5** below before installing any SaaS variant.

---

## Wave 1.5 — Self-hosted alternatives + production readiness (2026-05-15 addition)

Driven by the self-hosted operating context. Where a self-hosted equivalent exists, it should be the default — Wave 1 SaaS MCPs become opt-in only for cases where the self-hosted path is genuinely insufficient. Cross-reference: [`.claude/context/self-hosted-defaults.md`](../../../.claude/context/self-hosted-defaults.md).

### Self-hosted MCP substitutions

| Wave 1 SaaS item | Self-hosted alternative | Status / notes |
|------------------|------------------------|----------------|
| W1.3 Sentry MCP | **Glitchtip MCP** (self-hosted Sentry-compatible) at `errors.pmoves.ai` | Wave 1.5 — stand up Glitchtip on KVM4-2; reuse `mcp-server-sentry` (DSN-compatible) |
| W1.4 Linear MCP | **GitHub Issues MCP** (already covered by `github@claude-plugins-official`) + AGNOTE4482PHI.t1.md active claim register | No Linear needed — GitHub is the canonical issue tracker |
| W1.5 Brave Search MCP | **SupaSerch + DeepResearch internal**; if external web grounding is required, evaluate self-hostable SearXNG behind `search.pmoves.ai` | Defer Brave until SearXNG decision |
| W1.6 Cloudflare MCP | **Cloudflare MCP is itself acceptable** because the Cloudflare control plane is intrinsically SaaS. Scope to read-only token unless a specific Workers/R2 task needs write. | Approved — but use a least-privilege token |
| W1.1 Prometheus MCP | **Use as-is**; Prometheus IS self-hosted on KVM4-2 → no SaaS dependency. Point at `https://grafana.pmoves.ai/api/datasources/proxy/<id>/api/v1` or direct internal `http://kvm4-2:9090` over Tailscale. | Wave 1.5 — re-point env to internal URL |
| W1.2 Loki MCP | **Use as-is**; Loki self-hosted on KVM4-2. | Wave 1.5 — re-point env to internal URL |
| W1.8 Postgres MCP | **Use as-is** against self-hosted Supabase Postgres (port `:5432` on KVM4-2 over Tailscale). | Wave 1.5 — DB password via `/deploy:secrets-funnel` |
| W1.7 Playwright MCP | **Use as-is**; Playwright is local, no SaaS dependency. | Approved — install `npx playwright install` on ai-lab and KVM4-1 |
| W1.9 Fetch + Sequential-Thinking | **Use as-is**; both are local stdio. | Approved |

### OAuth wiring (Google + Supabase)

| # | Item | Status |
|---|------|--------|
| W1.5.1 | Enable Google OAuth provider in Supabase Studio (Auth → Providers) | Operator action |
| W1.5.2 | Register redirect URIs in Google Cloud Console | Operator action |
| W1.5.3 | Configure Supabase RLS for `archon_minted_artifacts` so rows are scoped by `creator_id = auth.uid()` | DB migration paired with W1.10 |
| W1.5.4 | Configure Supabase RLS for `archon_agents` and `archon_prompts.creator_id` FK | DB migration paired with W1.11 |
| W1.5.5 | Service-role keys for backend-to-backend (Archon mint subjects, Cipher writes) — NOT OAuth | Operator action — rotate quarterly via secrets-funnel |
| W1.5.6 | Document Supabase Auth → JWT claim → Archon role mapping (`creator` / `admin` / `agent`) | Doc PR |

### Production-readiness checklist (per minted artifact)

Every artifact emerging from Archon's mint MUST satisfy:

- [ ] No hardcoded `localhost:<port>` in operator-shipped config
- [ ] URLs use `*.pmoves.ai` or are env-var driven with prod default
- [ ] Auth (where present) = Supabase + Google OAuth (PKCE for SPAs)
- [ ] No SaaS provider chosen where a self-hosted equivalent exists (provider table in `self-hosted-defaults.md`)
- [ ] NATS subjects fit a branded namespace (`archon.*`, `chit.*`, `geometry.*`, `tokenism.*`, `p7.*`, `ingest.*`, `research.*`, `mesh.*`, `persona.*`)
- [ ] Service-to-service auth uses NATS user/pass OR Supabase service role OR mTLS — never OAuth
- [ ] Tier declaration (`dev` / `staging` / `prod`) present in manifest with env-var URL mapping

Enforced by `archon-qa-agent` (updated 2026-05-15 — see Wave-0.5 Task #11).

### Wave 1.5 deliverables

- [ ] `.claude/context/self-hosted-defaults.md` — branded URLs, OAuth wiring, provider preferences. **Done 2026-05-15.**
- [ ] `archon-qa-agent` branded-defaults audit step. **Done 2026-05-15.**
- [ ] Google OAuth wiring documented in `/archon:mint-agent`, `/archon:mint-skill`, `/archon:creator-onboard`. **Done 2026-05-15.**
- [ ] Glitchtip stand-up on KVM4-2 (operator action; not Claude-authorable).
- [ ] SearXNG decision (defer to Wave 2 if SupaSerch is sufficient).

---

## Wave 2 — Service-side implementation (separate PRs)

| # | Item | Owner service |
|---|------|---------------|
| W2.1 | Define `archon.mint.agent.v1` / `mint.skill.v1` / `mint.creator.v1` / `mint.confirmed.v1` / `qa.result.v1` subjects + publishers | PMOVES-Archon |
| W2.2 | Implement `POST /api/agents` + corresponding MCP tool | PMOVES-Archon |
| W2.3 | Implement `POST /api/artifacts` for minted artifact registry | PMOVES-Archon |
| W2.4 | Implement `archon-qa-agent` orchestration on `archon.work_order.github.v1` consume | Agent Zero |
| W2.5 | Build `pmoves-governance` MCP (Village Rule body presence) | New service |
| W2.6 | Add CHIT integration to remaining 15 "None" services | per-service |
| W2.7 | docs-reconcile-hook wired into `merge-gate.yml` GH workflow | CI |

---

## Verification

After Wave 0:
1. Run `git submodule status skills/` — all 5 should show `+` or no prefix (initialized).
2. List skills: each new SKILL.md should appear if the harness scans `.claude/skills/` (or operator runs `/skills` to confirm). Files exist either way.
3. Run `bash .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh` — observe table output.
4. Run `bash .claude/hooks/governance/signoff-gate.sh < /tmp/test-payload.json` — verify exit 2 when ACKs absent.
5. Verify `pmoves-nats-mcp` builds cleanly: `cd pmoves-nats-mcp && uv sync && uv run python -m nats_mcp.server --help`.
6. Commit graph shows 11 atomic commits, one per task.

---

## Out of scope for this plan

- Building the live `archon:create-agent` MCP tool (depends on W2.2 service work).
- Building the `pmoves-governance` Village Rule MCP (depends on W2.5).
- Three-body NATS-backed quorum (depends on Wave 2).
- `pmoves-floos-lint` skill (FlOO$ Phase A/B/C spec still landing per commit `6c77be860`; revisit after Phase A merges).
- Live API-key MCP installs (Wave 1).

## Self-review

✅ Spec coverage: All 35 gap items mapped to Wave 0/1/2.
✅ No placeholders: Each step has concrete file paths and shell commands.
✅ Type consistency: NATS MCP tool names (`nats_publish`, `nats_subscribe`) used consistently. Skill names use kebab-case throughout.
✅ Wave 0 is fully autonomous; Wave 1/2 dependencies surface as explicit operator actions.
