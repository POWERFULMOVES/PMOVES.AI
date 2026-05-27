# Archon — Subsystem Context

> Subsystem-specific CLAUDE.md. Load on demand when working inside `pmoves/services/archon/`. README has the operator-facing setup; this doc captures the developer-facing model for Claude.

## Identity

**Role**: Agent factory + creator mint for PMOVES.AI. Tracks prompts, forms, and (Wave 1) minted artifacts in Supabase. Exposes MCP for Agent Zero and other clients.

**Ports**: API/UI `:8090`, MCP bridge `:8051`, agents/workers `:8052`. (Note: `.claude/CATALOG.md` documents the published `:8091` / `:3737` external mapping — the internal container ports are `:8090` / `:8051` / `:8052`.)

**Vendored**: Upstream Archon code lives at `pmoves/services/vendor/archon/` (cloned at image build from a POWERFULMOVES fork; override via `ARCHON_GIT_REMOTE`/`ARCHON_GIT_REF`).

## Wave-trajectory: factory → mint

PMOVES.AI's roadmap (`docs/superpowers/plans/2026-05-15-pmoves-gap-fill-roadmap.md`) tracks Archon's evolution into the canonical mint for new agents/skills/creators:
- **Wave 0 (PR #1490)** — scaffold the mint slash commands (`/archon:mint-agent`, `/archon:mint-skill`, `/archon:creator-onboard`), QA subagent (`.claude/agents/archon-qa-agent.md`), branded-defaults audit step.
- **Wave 1** — Supabase schema (`archon_minted_artifacts` table + `agent_id` FK on `archon_prompts`), Google OAuth via Supabase Auth.
- **Wave 2** — `POST /api/agents`, mint NATS subjects, `archon-qa-agent` orchestration.

When editing Archon code, check which wave the change belongs to and gate accordingly.

## Auth (Wave 0.5 wiring)

- Identity provider: **Google OAuth via Supabase Auth** (PKCE for SPAs). Never roll a custom auth flow.
- Service-to-service: NATS user/pass (`nats:pmoves`) or Supabase service role keys — **not** OAuth.
- Mint commands require an authenticated creator session; RLS in Wave 1 will enforce `creator_id = auth.uid()`.
- See `.claude/context/self-hosted-defaults.md` § "Authentication".

## NATS subjects (current + planned)

Current (Wave 0):
- `archon.crawl.*` — crawl pipeline
- `persona.publish.v1`, `persona.update.v1` — persona pipeline
- `archon.work_order.github.v1` — work order consume

Planned (Wave 2):
- `archon.mint.agent.v1`, `archon.mint.skill.v1`, `archon.mint.creator.v1` — mint emit
- `archon.mint.confirmed.v1` — post-QA confirmation
- `archon.qa.result.v1` — QA gate output

Auditor: `.claude/agents/nats-subject-auditor.md` reviews new subjects against `.claude/context/nats-subjects.md` + branded namespace rules.

## Supabase

Uses CLI stack on `pmoves-net`. Internal hostname `http://postgrest:3000` is auto-rewritten by the Archon wrapper (`ARCHON_HTTP_ALLOW_HOSTS` env). Service role key required (`SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_KEY`). See README for full env-var table.

## CHIT integration

**Status: None** per `pmoves/docs/audit/CHIT_INTEGRATION_STATUS.md` (2026-03-24 snapshot). Archon does NOT directly sign CHIT trails — it operates over search/retrieval, and CHIT packets are produced/consumed by Hi-RAG gateways instead. The mint flow (Wave 2) WILL publish `archon.mint.*.v1` and `chit.signed.v1` events; those subjects are CHIT-aware via downstream consumers.

When modifying Archon, do not invent CHIT signing here. If a code path needs CHIT, route through Hi-RAG or the (Wave-2) mint NATS subjects.

## Common tasks

- **Add a mint subject publisher**: extend `services/archon/<module>.py`, ensure subject is registered in `.claude/context/nats-subjects.md`, run `/tac:review archon` to verify TAC tree compliance.
- **Modify Supabase access**: prefer service role key paths over PostgREST hostname rewrites. The `ARCHON_HTTP_ALLOW_HOSTS` mechanism is fragile.
- **Add a new persona form**: drop YAML into `ARCHON_FORMS_DIR` (default `configs/agents/forms/`); restart `archon` container.
- **Debug**: `docker logs pmoves-archon`; health at `GET /healthz` (`:8091` external).

## Cross-references

- README: `pmoves/services/archon/README.md` — operator setup, env vars.
- TAC tree: `pmoves/docs/TAC/TAC_AGENT_ZERO.md` (Archon shares the agent-coordination TAC family; no dedicated TAC tree yet — TODO).
- Mint slash commands: `.claude/commands/archon/{mint-agent,mint-skill,creator-onboard}.md`.
- QA subagent: `.claude/agents/archon-qa-agent.md`.
- Service catalog entry: `.claude/CATALOG.md` § "Agent Coordination & Orchestration".
- Self-hosted defaults: `.claude/context/self-hosted-defaults.md`.
