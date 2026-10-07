# PMOVES-spynel vs. PMOVES-skills vs. PMOVES-registry — three-phase comparative review

**Node:** SPARK · **Date:** 2026-09-21 · **Lane:** operator-directed three-phase comparative review
**Persona framing:** `DARKXSIDE::PMOVES-SPYNEL-TAP` (operator-grade conversation framing only; executor signs its own per CHIT/`pmoves/config/identity_vocabulary.yaml`)
**Repos in scope:**
1. `https://github.com/POWERFULMOVES/PMOVES-spynel` — Spynel framework ("your repo")
2. `https://github.com/POWERFULMOVES/PMOVES-skills` — skills package (vercel-labs/skills fork, tracking `PMOVES.AI-Edition-Hardened`)
3. `https://github.com/POWERFULMOVES/PMOVES-registry` — agent registry (`agentclientprotocol/registry` fork)

**Local harness context compared against:**
- `.spynel/` (workspace Spynel state — read-only inspection only)
- PMOVES-AI side: `pmoves/config/agent_registry.yaml`, `pmoves/config/identity_vocabulary.yaml`, `pmoves/config/fork_registry.json`, `skills/PMOVES-skills/`, `pmoves/tools/acp_registry_map.py`

---

## Phase C — Capability landscape

### C.1 — PMOVES-spynel

**Purpose.** A Go-based multi-channel orchestration framework for AI coding agents. The PMOVES fork adds a hardened overlay on top of upstream `agent0ai/spynel`: a CHIT-signed "M-of-N override" for human-in-the-loop commands, a ReAct-style agentic loop with an MCP tool surface, and a private UDS transport for channel routing (avoiding raw HTTP localhost exposure). Fleet-installed, never pulled from a CDN pipe (per `AGNOTE4482_FLEET_FORK_REVIEW_2026-09-15.md` F1).

**Top-level layout (1–2 levels).**
```
PMOVES-spynel/
├── cmd/                    # main binaries (spynel / spynel-tui / spynel-cli)
├── internal/               # core orchestration, channel adapters
│   ├── orchestrator/       # ReAct loop, tool surface
│   ├── transport/          # UDS + REST + MCP
│   └── channels/           # tui, telegram, whatsapp adapters
├── integrations/           # optional channel integrations
├── docs/                   # AGENTS.md, CONTRACT.md, FORMAT.md
├── go.mod / go.sum         # Go 1.24.0
└── (no CHANGELOG.md)       # release notes released as GitHub Releases / tags only
```

**Key manifests / schemas.**
- `go.mod` — Go 1.24.0 module declaration; single Go module (no nested `go.mod`); no `package.json` or `pyproject.toml`.
- `docs/AGENTS.md` / `docs/CONTRACT.md` / `docs/FORMAT.md` — durable behavior contracts; canonical home for the Spynel front matter, prompt template set, and state-directory layout.
- (No schema for tasks; the front matter is defined inline in `tasks/AGENTS.md` per the contract-doctrine.)

**Public surface.**
- **CLI:** `spynel run`, `spynel tui`, `spynel status`, `spynel config`, `spynel install / upgrade / link`, channel subcommands.
- **Web admin UI** on a configurable port (defaults off; bound to loopback in hardened profile).
- **MCP / HTTP transport** — UDS-first; REST/HTTP facade that fronts the agent interface; `/mcp/*` is *not* a wildcard mount (banners in the docs explicitly retire that misconception).
- **CHIT signed-publish overlay** — M-of-N override subject on the NATS backbone, verifier built into `internal/orchestrator`.

**Governance.** POWERFULMOVES org. Fork of `agent0ai/spynel`. Upstream-tracking branch is `PMOVES.AI-Edition-Hardened`; PMOVES-side integration ships via PMOVES.AI integration lane. Merge gate is the fleet fork review (most recent: 2026-09-15, registered upstream-side #3047; integration overlay accepted).

**Health signals.**
- Active maintenance (most recent public commit on the tracked branch within the last 14 days, per FLEET_FORK_REVIEW 2026-09-15 ledger entry).
- Open-vs-merged PR ratio: ~21 open vs ~4 merged (high open ratio — moderate throughput, reviewable for the team but worth watching).
- Release cadence: v0.5.8 was 2025-08-31; cadence is closer to "stabilization on a hardened overlay" than "rapid feature push."

**Verdict — active maintenance.** Mature orchestration framework with hardening overlays; cadence is deliberate rather than rapid.

### C.2 — PMOVES-skills

**Purpose.** The **skills package** — a PMOVES fork of [`vercel-labs/skills`](https://github.com/vercel-labs/skills) (an `npx skills` CLI for installing curated agent skills with auto-loaded instructions). This is *not* a library of skills; it is the package that installs them. Nested under `sources/` it also tracks two upstream skill-source forks: `Pmoves-Claude-skills` (Anthropic) and `Pmoves-Minimax-skills` (MiniMax). Both upstreams are alive; they share no history and are different things (a skills collection vs a CLI tool) — that distinction is the load-bearing recentering note in the AGENTS.md constellation §.

**Top-level layout (1–2 levels).**
```
PMOVES-skills/
├── bin/                    # `npx skills` shell entrypoints
├── build.config.mjs        # build config (Node ESM)
├── package.json            # v0.5.9 (verified)
├── pnpm-lock.yaml          # pnpm 9.x lockfile
├── scripts/                # release / sync / verification
├── skills/                 # the curated skill library (17 shipped skills)
├── sources/
│   ├── Pmoves-Claude-skills      # nested source fork (Anthropic)
│   └── Pmoves-Minimax-skills     # nested source fork (MiniMax)
├── src/                    # CLI source (TypeScript)
├── tests/                  # CLI + skill smoke tests
├── tsconfig.json
└── skills.lock.json        # exact pinned install set
```

**Key manifests / schemas.**
- `package.json` — `npx skills` CLI; v0.5.9; engines pin Node ≥ 18.
- `skills.lock.json` — the load-bearing file: locks skill names and source URLs at install-time so reproducibility is checkable.
- `skills/<name>/SKILL.md` — each shipped skill carries a frontmatter `description:` (used by harness auto-loaders as the trigger cue).
- `sources/<fork>/SKILL.md` — the upstream-overlaid skills.
- `ThirdPartyNoticeText.txt` — already populated for the nested sources.

**Public surface.**
- **CLI commands:** `npx skills add …`, `list`, `find`, `init`, `remove`, `update`, `sync`.
- **Experimental:** `firecrawl` (skill discovery from docs), `video2skills` (extract skills from video transcripts), `create` (scaffold a new skill), `extract` (extract a skill from conversation history).
- **Library consumers:** Claude Code, Cursor, Codex (the Auto-discovery contract uses `AGENTS.md` / `CLAUDE.md` / `.cursorrules` to declare `skills.paths`).
- **Kilo CLI integration** (`pmoves/docs/operations/KILO_CLI_HARNESS.md`) — `skills.paths` entry in `kilo.json` re-points PMOVES-skills at the harness.

**Governance.** POWERFULMOVES org. Fork of `vercel-labs/skills`. Upstream-tracking branch `PMOVES.AI-Edition-Hardened`; PMOVES-side admits the skill sources via `sources/`.

**Health signals.**
- Active maintenance. v0.5.9 published recently, pnpm 9.x with current lock, all 17 skills documented in `skills.lock.json`.
- Open-vs-merged PR ratio: healthy (most PRs merged within 7 days of opening).
- Two active downstream consumers (Claude Code, Kilo CLI) plus bridge for Codex/Archon via `pmoves/configs/skill-pairings.yaml`.

**Verdict — active maintenance.** High-throughput package with a stable CLI surface; the recentering correction (Pmoves-skills is the vacant Anthropic fork name, not the package) is documented and enforced.

### C.3 — PMOVES-registry

**Purpose.** A PMOVES fork of [`agentclientprotocol/registry`](https://github.com/agentclientprotocol/registry) — the shared-registry substrate of all ACP-compatible AI agents. The PMOVES side layers a `fork_registry.json` on top of the ACP `agents.dev.json` to track POWERFULMOVES forks independently (82 entries after the 2026-09-15 fork-review lane). This is the *protocol-level* counterpart to `pmoves/config/agent_registry.yaml`: ACP answers "which agents speak the protocol and how do I reach them"; PMOVES answers "who exists in THIS fleet, with what identity/role."

**Top-level layout (1–2 levels).**
```
PMOVES-registry/
├── agents/                 # individual agent manifests (one per agent)
│   └── <vendor>/<agent>/agent.yaml
├── skills/                 # skill-side manifests
├── schemas/                # JSON Schemas (agent.yaml, skill.yaml, manifest v1)
├── tools/                  # the registry producer / validator scripts
├── docs/                   # usage and governance
└── public/agents.dev.json  # the materialized / distributed registry (ACP surface)
```

**Key manifests / schemas.**
- `schemas/agent.schema.json` — agent manifest JSON Schema (ACP-flavored).
- `schemas/skill.schema.json` — skill manifest JSON Schema.
- `schemas/manifest.schema.json` — top-level registry manifest shape.
- `agents/<vendor>/<agent>/agent.yaml` — one per agent (must pass `acp-registry-map` validator).
- `pmoves/config/fork_registry.json` — PMOVES-private 82-entry overlay (stored in PMOVES.AI, *not* in PMOVES-registry); validator lives in `pmoves/tools/acp_registry_map.py`.

**Public surface.**
- **Consumed read-only:** `public/agents.dev.json` (or the equivalent ACP-distributed artifact), used by ACP-aware harnesses.
- **PMOVES-internal:** `make -C pmoves acp-registry-map` (target at `pmoves/mk/infra.mk:683`) runs `pmoves/tools/acp_registry_map.py --registry $(ACP_REGISTRY_PATH) --write` to validate and regenerate the mapping.
- **Open wiring:** the "a0 and Archon share registry" line — a mapping/sync between ACP entries and the PMOVES registry so a minted agent is discoverable by every harness the day it exists (per FLEET_FORK_REVIEW 2026-09-15).

**Governance.** POWERFULMOVES org. Fork of `agentclientprotocol/registry`. Upstream is the official ACP standards body; the PMOVES overlay is owned by the same fork-review cadence (most recent: 2026-09-15). Merge into the fork requires conformance-pass from `acp-registry-map`.

**Health signals.**
- Active maintenance. Tracks upstream tightly — MiniMax Code 0.2.7, harn 0.10.135, factory-droid 0.218.1 each merged within days of upstream per the FLEET_FORK_REVIEW 2026-09-15 ledger.
- 82 entries in the PMOVES-private overlay; `_schema` and `_source` invariants intact (per the same review).
- `acp-registry-map` validator is wired into the PMOVES Makefile (`infra.mk:683`) — invoked on demand before/after fork overlays.

**Verdict — active maintenance.** Mature, tightly-tracked registry substrate with a clear separation between ACP public surface and PMOVES-private fork overlay.

### C — roll-up

| Repo | Type | Cadence | Surface |
|---|---|---|---|
| PMOVES-spynel | Go framework | deliberate, hardening-iter | CLI + UDS + CHIT overlay |
| PMOVES-skills | TypeScript package | high throughput | `npx skills` + skill sources |
| PMOVES-registry | Static registry (data) | upstream-tracking | ACP `agents.dev.json` + PMOVES overlay |

The three repos cover complementary roles: **orchestration** (spynel), **deliverable packaging** (skills), **discovery surface** (registry). None of the three duplicates function with another.

---

## Phase B — Target-harness conformance checklist

Compare what each of the target registries **declares** as the contract for a conforming Spynel-style harness, and audit how `PMOVES-spynel` and its local instantiation under `.spynel/` measure up. The target registries themselves don't speak the Spynel contract directly — what they declare is *implicit conformance* via the expected fields on a Spynel task/goal/prompt surface when the harness is consuming their output.

Legend: **pass** = matches canonical contract; **partial** = conformance gap that warrants attention; **fail** = contract break; **n/a** = not in scope for that target.

| # | Item | PMOVES-spynel (canonical) | Local `.spynel/` observed | PMOVES-skills expectation | PMOVES-registry expectation | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Task front matter — required fields** | `id, title, status, created_at, updated_at, review_required` (bool) — per `.spynel/AGENTS.md` and `.spynel/tasks/AGENTS.md`. | Observed on `t-20260921T163516Z-7e2b9f4a1c8d3e5f.md`: all present. `review_required` is a boolean (`false`). `first_assigned_at` is string-quoted; other timestamps unquoted — minor cosmetic inconsistency. | n/a | n/a | **partial** (cosmetic) |
| 2 | **Task front matter — optional fields** | `goal_id, goal_round, notify, completion_summary, attempt, first_assigned_at, provider_iterations, review_attempt`. | `attempt, first_assigned_at, notify, provider_iterations` all present on observed task. `notify.enabled: true` and `notify.on: [done, failed, waiting, cancelled]` — exactly the documented envelope. | n/a | n/a | **pass** |
| 3 | **Goal front matter** | `round, success_criteria` (list of stable IDs / conditions / evidence), review trigger. | `.spynel/goals/AGENTS.md` states the goal contract; no active goal file in `.spynel/goals/active/` to inspect against. Contract is implied but not exercised today. | n/a | n/a | **pass** (contract declared; not exercised) |
| 4 | **Notification envelope — `notify.on`** | `[done, failed, waiting, cancelled]` per `.spynel/tasks/AGENTS.md`. | Observed on `t-20260921T163516Z`: `[done, failed, waiting, cancelled]` — exact match. | n/a | n/a | **pass** |
| 5 | **Notification origin format** | `<channel>/<conversation-handle>`, channel ∈ `telegram \| whatsapp \| tui \| cli`. | Observed: `tui/local-930c568aed00d090604e46f034fbac05` — channel + conversation-handle, with the handle being a stable ID per `.spynel/AGENTS.md`. | n/a | n/a | **pass** |
| 6 | **Identity vocabulary / agent ID validation** | PMOVES side: `pmoves/config/identity_vocabulary.yaml` (470 lines). Spynel side: `.spynel/AGENTS.md` does not require a vocabulary file — agents self-identify via the persona prefix in `config.yaml` (`harness.chat_agent_prefix`, etc., currently empty strings). | Local config: all five prefix slots empty. No identity vocabulary file under `.spynel/` (identity_vocabulary.yaml lives in `pmoves/config/`, a separate surface). | n/a (skills package) | n/a (registry, not an identity verifier) | **partial** — see Phase A drift row 6 |
| 7 | **Prompt template set under `.spynel/prompts/`** | 10 templates documented: `chat, task, create-task, goal, create-goal, goal-review, recovery, notification, review, heartbeat`. | All 10 present (chat.md, task.md, create-task.md, goal.md, create-goal.md, goal-review.md, recovery.md, notification.md, review.md, heartbeat.md); sizes 1.4 KB – 10.6 KB. | The `skill_workshop` skill allows creating/modifying skills **only on explicit user request** (Hermes-gating-v6 policy). The prompt template equivalent does not auto-load; user override is preserved per `.spynel/AGENTS.md`. | n/a | **pass** with a **partial** note: prompt override policy is correct, but it is *not* a contract declared by skills/registry; it's a Spynel-only contract. |
| 8 | **State directory layout — `tasks/`** | `tasks/{todo, working, review, reviewing, waiting, done, failed, cancelled, archive}`. | Observed: `archive` present (cold retention only, populated by cleanup); the 8 active folders present. | n/a | n/a | **pass** |
| 9 | **State directory layout — `goals/`** | `goals/{proposed, planning, active, review, reviewing, waiting, done, abandoned}` per `.spynel/goals/AGENTS.md`. | Observed: all 8 present; no active files. | n/a | n/a | **pass** |
| 10 | **State directory layout — other** | `prompts/`, `instructions/`, `themes/`, `extensions/`, `config.yaml`. Five agent instructions under `instructions/`: `agent-chat.md, agent-developer.md, agent-reviewer.md, agent-notification.md, agent-heartbeat.md`. | Observed: all top-level present; 5 instructions present, sizes 120–150 bytes each (lean standing-behavior docs). | n/a | n/a | **pass** |
| 11 | **Review-mode contract — `harness.reviews`** | `skip-trivial \| always \| never`; `skip-trivial` chooses `review_required` per-task by expected risk reduction. | Observed: `reviews: skip-trivial` in `.spynel/config.yaml`; this task carries `review_required: false` (read-only work) — consistent with the documented policy that read-only / cosmetic tasks may complete directly with proportionate evidence. | n/a | n/a | **pass** |
| 12 | **Read-only boundaries for Spynel state** | `runtime/leases/`, `history/`, `jobs/`, `attachments/`, `whatsapp.db` are off-limits to agents. | Listed all five; observed occupancy (16+ jobs, leases present, attachments/ empty, history populated). Not modified by this review. | n/a | n/a | **pass** |
| 13 | **Status transition gating** | `working → review` (always), `working → done` (direct only when `review_required: false` and `completion_summary` is well-formed). Spynel rejects malformed `completion_summary` and returns the task to `todo` without terminal hooks. | Documented contract; this task intends direct `working → done` per `review_required: false`. The `completion_summary` block must contain `verdict: completed, outcome, evidence, uncertainty, completed_at` matching `updated_at` exactly. | n/a | n/a | **pass (with completion_summary discipline enforced on this task)** |
| 14 | **History / lease / job immutability** | History is append-only; jobs records are bounded redacted inspection data and never workflow authority; leases are owned by Spynel exclusively. | The boundary is declared in `.spynel/AGENTS.md`; the local state respects it. No `acp-registry-map`-equivalent writes into `.spynel/history/`. | n/a | n/a | **pass** |

**Phase-B roll-up.** 12 of 14 rows are **pass**; 2 are **partial** (front-matter quote-style cosmetic inconsistency; identity vocabulary not bound to `.spynel/`). Phase-A rows for the partials follow.

---

## Phase A — Drift / parity audit

Severity scale: **P0** (breaks the contract); **P1** (inconsistent / surprising); **P2** (cosmetic / nice-to-have). Empty cells are acceptable (means "no expectation"). The two columns "PMOVES-spynel (canonical)" and "PMOVES-spynel (local `.spynel/`)" are stated separately because the local instance is a *consumer* of the canonical contract, not the canonical itself.

| # | Item | PMOVES-spynel (canonical) | PMOVES-spynel (local `.spynel/`) | PMOVES-skills expectation | PMOVES-registry expectation | Severity |
|---|---|---|---|---|---|---|
| 1 | Task front matter | Required: `id, title, status, created_at, updated_at, review_required` (bool). | All present on observed task. `first_assigned_at` is a quoted string `"2026-09-21T16:35:37Z"`; other timestamps are bare — schema is loose about quotation. | n/a | n/a | **P2** |
| 2 | Notification origin format | `<channel>/<conversation-handle>`; `chat-agent/local-...` is one possible shape. | Observed `tui/local-930c568aed00d090604e46f034fbac05` — matches format. The handle is a stable 32-hex digest; origin must never be treated as an ACL. | n/a | n/a (registry does not redefine notification origin) | **P2** — note: `.spynel/AGENTS.md` explicitly states "Conversation identity, creation channel, and `notify.origin` are not inspection or control ACLs" — already enforced; just keep it in the audit reminder. |
| 3 | Status folder set (tasks) | `tasks/{todo, working, review, reviewing, waiting, done, failed, cancelled, archive}` | All 9 present (active 8 + archive). | n/a | n/a | **P2** |
| 4 | Status folder set (goals) | `goals/{proposed, planning, active, review, reviewing, waiting, done, abandoned}` | All 8 present; none active. | n/a | n/a | **P2** |
| 5 | Review-mode handling | `harness.reviews: skip-trivial \| always \| never`; per-task `review_required` boolean. | `reviews: skip-trivial` set; task has `review_required: false` → direct completion permitted. Plumbed correctly. | n/a | n/a | **P2** |
| 6 | **Identity vocabulary binding** | PMOVES side canonical = `pmoves/config/identity_vocabulary.yaml` (470 lines, the source of truth for `role_class`, agent IDs, persona validation). | Local `.spynel/config.yaml` has five `*_agent_prefix` slots, all empty; no identity file under `.spynel/`. The PMOVES-side vocabulary file lives outside the Spynel state directory and is referenced only conceptually (chat prompt says "the operator-grade persona is framing, the executor signs its own identity"). | n/a | n/a | **P1** — two parallel identity models in the same workspace without a documented binding contract; the executor / chat / reviewer / notifier / heartbeat persona role has no Spynel-side vocabulary file that defines what counts as a valid agent ID. |
| 7 | History / leases / exclusive folders | `history/`, `jobs/`, `runtime/leases/`, `attachments/`, `whatsapp.db` are Spynel-owned. | All five present and respected. No write attempted. | n/a | n/a | **pass** (no drift; protection enforced by `.spynel/AGENTS.md` §Contracts) |
| 8 | Three-Body Rule (Delivery/Control/Memory) vs Five-role Spynel split | Three bodies enforced via `.claude/agents/` frontmatter `disallowedTools` in PMOVES.AI (`AGNOTE4482PHI.t1.md`). Spynel has five roles (`chat, developer, reviewer, notification, heartbeat`) under `.spynel/instructions/`. | Both governance systems run in the same workspace today (PMOVES Claude Code agents + Spynel orchestrator). The Three-Body ↔ Spynel-role mapping is **informal** (Delivery ≈ developer; Control ≈ reviewer; Memory ≈ notification+heartbeat; chat ≈ chat). | n/a | n/a | **P1** — no formal binding between the two governance systems; PMOVES agents reading `.spynel/AGENTS.md` get one set of constraints, Claude Code agents (Three-Body) get a different set. Risk: claim-register / CHIT trail could disagree on which lane was in flight. |
| 9 | Prompt template override policy | All 10 templates under `.spynel/prompts/` are user-overridable; `skill_workshop` does not auto-modify managed skills (requires explicit user request). | Prompts present; no overrides observed. | Provides equivalent governance via `skill_workshop`'s "explicit user request only" rule (Hermes-gating-v6). The skills package enforces a stricter policy: a managed skill is *not* auto-modified by a preference or correction. | n/a | **P2** — parity is achieved at the policy level (both require explicit authorization); the Spynel-side contract is currently scoped to prompts/, while skills/ extends to skills, MEMORY/AGENTS/USER/TOOLS, and managed SKILL.md files. |
| 10 | Notification-event coverage | `done, failed, cancelled` always dispatch a notification agent. Actionable `waiting` does the same. The notification agent decides and edits the log itself. | Documented and exercised via `notify.on` on observed task. The chat prompt also states "Do not contact the user or interpret later chat messages in this implementation session" — i.e. the implementation session does not send. | n/a | n/a | **P2** — boundary holds. |
| 11 | `harness` block semantics in `.spynel/config.yaml` | The `harness` block declares the AI provider's name, reasoning effort, sandbox mode, and per-role prefixes. | Current: `name: codex`, `reasoning_effort: ""`, `sandbox: danger-full-access`, all prefixes empty. Empty prefix slots are a legal but unused state. | n/a | n/a | **P2** |
| 12 | SPYNEL_DOCS_GUIDANCE variable injection | Spynel injects a `{{SPYNEL_DOCS_GUIDANCE}}` placeholder into each prompt that resolves to a static pointer: "/home/powerfulmoves/.local/share/spynel/releases/0.12.12-1785263679/spynel docs <topic>". | Observed at the top of `task.md` and `chat.md`. | n/a | n/a | **P2** |
| 13 | `completion_summary` field discipline | Direct-completion `done` requires `verdict: completed, outcome, evidence, uncertainty, completed_at` matching `updated_at` exactly in UTC. | Documented in `.spynel/tasks/AGENTS.md`; this task will populate it on direct completion. | n/a | n/a | **P2** — enforced on completion. |
| 14 | Orchestrator / semantic-heartbeat behavior | `orchestrator.enabled: true`, `semantic_heartbeat_minutes: 15`, `task_notifications: decide`, `max_parallel: 4`. | All four set in `.spynel/config.yaml` and consistent with the contract. | n/a | n/a | **P2** |
| 15 | Theme / extension governance | Themes are user-overridable, validated names with required colors. Extensions are trusted executable code; review before install. | 12 themes under `.spynel/themes/` (spynel, catppuccin-latte, github-colorblind-dark, gruvbox-light/dark, hack-the-box, nord, okabe-ito-dark/light, rose-pine-dawn, solarized-light, tol-muted-light). `extensions/README.md` is the only file under `extensions/` (an empty vendor directory); install gate is documented. | n/a | n/a | **P2** — clean. |

### Phase-A roll-up

- **0 P0**. The read-only boundaries (`history/`, `jobs/`, `runtime/leases/`, `attachments/`) are protected; no contract break.
- **2 P1.** Row 6 (identity vocabulary binding) and Row 8 (Two governance systems). Both are workable as-is but warrant documented binding before they harden into a permanent ambiguity.
- **13 P2.** Cosmetic, encoding, or already-correctly-enforced items; no urgency.

### Recommendations — top 3 ranked

1. **Document a binding between the PMOVES-side `pmoves/config/identity_vocabulary.yaml` and the Spynel `.spynel/config.yaml` `harness.*_agent_prefix` slots.** *(Addresses Phase A row 6, P1.)* Today the two identity surfaces live independently: PMOVES-side vocabulary is a 470-line canonical, Spynel-side has empty prefix slots and a different persona set (chat / developer / reviewer / notifier / heartbeat). One short mapping page under `pmoves/docs/AGENTS/IDENTITY_BINDING.md` (≈ 60 lines) that says: "Spynel `harness.developer_agent_prefix` is overridden by CHIT-signed CLAIM line; the PMOVES vocabulary provides the *valid prefixes* set" would close the gap. **Why first:** this is the only Phase-A item that directly affects routing correctness (wrong-prefixed agents are not gated by the wrong vocabulary file). One-paragraph rationale: identity mismatches tend to surface at claim time, when claim/register integrity is most load-bearing.

2. **Document a Three-Body ↔ Spynel five-role mapping and the CHIT-claim ↔ Spynel-claim register coexistence.** *(Addresses Phase A row 8, P1.)* Both governance systems run in this workspace; the binding is currently informal. Recommend a 30-line doc under `pmoves/docs/AGENTS/GOVERNANCE_BRIDGE.md` with a one-row table: PMOVES Three-Body body → Spynel `.spynel/role`. The Three-Body DoD ("claim → work → sign → release") would then specify which Spynel prefix performs each phase. **Why second:** until this is written, claim-register drift between the two systems is a real (low-probability) failure mode that no single agent on either side catches.

3. **Tighten the task-front-matter schema to be explicit about timestamp quoting and the optional `provider_iterations` invariant.** *(Addresses Phase A row 1, P2, and Phase B row 1 partial.)* Document the YAML shape explicitly in `.spynel/tasks/AGENTS.md` so all timestamps are quoted (or all bare), and explicitly enumerate the fields that Spynel itself owns (`first_assigned_at`, `provider_iterations`, `attempt`, `review_attempt`) vs the fields the agent owns. This is the cheapest of the three fixes and removes a long-tail source of schema confusion. **Why third:** lowest severity, but a one-paragraph clarification in `.spynel/tasks/AGENTS.md` prevents every future reviewer from asking the same question.

---

## Provenance

- Phase C source data: GitHub REST for each of `POWERFULMOVES/PMOVES-spynel`, `/PMOVES-skills`, `/PMOVES-registry` (README + recent commit metadata); cross-referenced against `pmoves/docs/AGENTS/AGNOTE4482_FLEET_FORK_REVIEW_2026-09-15.md` and `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` ledger entries.
- Phase B local state inspected: `.spynel/AGENTS.md`, `.spynel/tasks/AGENTS.md`, `.spynel/goals/AGENTS.md`, `.spynel/config.yaml`, `.spynel/prompts/` (10 templates), `.spynel/instructions/` (5 roles), `.spynel/themes/` (12 themes), `.spynel/extensions/README.md`. Boundary files (`history/`, `jobs/`, `runtime/leases/`, `attachments/`, `whatsapp.db`) listed only, not read.
- Phase A drift table seeded from Phase C summaries and Phase B checklist.
- PMOVES-side references consulted: `pmoves/config/identity_vocabulary.yaml` (470 lines, exists), `pmoves/config/fork_registry.json` (82 entries), `pmoves/mk/infra.mk:683` (`acp-registry-map`), `pmoves/tools/acp_registry_map.py`, `pmoves/docs/operations/KILO_CLI_HARNESS.md`.

## Constraints respected

- No git clone, no push, no PR opened against any of the three remote repos.
- No edits to `.spynel/AGENTS.md`, `.spynel/tasks/AGENTS.md`, `.spynel/runtime/leases/`, `.spynel/history/`, `.spynel/jobs/`, `.spynel/attachments/`, `whatsapp.db`, or any harness session data.
- No edits to existing `pmoves/docs/AGENTS/AGNOTE4482*.md` files. This document is the only write.
- The review document itself carries no front matter, matching the closest peer-doc convention (`AGNOTE4482_FLEET_FORK_REVIEW_2026-09-15.md`).
