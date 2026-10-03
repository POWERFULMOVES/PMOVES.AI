# Governance Bridge — PMOVES Three-Body ↔ Spynel five-role

Two governance systems run in this workspace. This page records how they line up **as they are today**, and names the gaps rather than inventing correspondences. Satisfies recommendation #2 (P1) of `pmoves/docs/AGENTS/PMOVES-SPYNEL-VS-REGISTRIES-REVIEW-2026-09-21.md:208`. All citations are superproject state; nothing here claims anything about submodule code.

## Body → role mapping

Three bodies against five roles is not a bijection. Two bodies have a usable Spynel counterpart, one has none, and three Spynel roles have no Three-Body counterpart.

| Three-Body body | Spynel role (`.spynel/AGENTS.md:14`) | Relationship |
|---|---|---|
| **Delivery** — execution lane (`AGNOTE4482PHI.t1.md:20`) | `agent-developer` | Closest to a true pair: each is the only writing body in its system. |
| **Control** — governance lane, read-only (`AGNOTE4482PHI.t1.md:26`) | `agent-reviewer` | Partial. Control also owns merge sequencing and branch-pruning policy; the Spynel reviewer's authority stops at one task document (`.spynel/tasks/AGENTS.md:27`). |
| **Memory** — Cipher/CHIT custody and signature trail (`AGNOTE4482PHI.t1.md:32`) | **none** | Spynel has no memory or custody role. CHIT custody stays PMOVES-side via `.claude/agents/memory-agent.md`. |
| **none** | `agent-chat` | Communication dispatcher — records tasks and goals, delegates execution. Runs *before* any lane exists (`.spynel/AGENTS.md:15`). |
| **none** | `agent-notification` | Outbound delivery decision on terminal and actionable-waiting transitions (`.spynel/tasks/AGENTS.md:29`). |
| **none** | `agent-heartbeat` | Non-overlapping primary-owned workflow audit (`.spynel/AGENTS.md:21`). |

## Per-phase prefix notes

The Three-Body DoD is `claim → work → sign → release` (`AGENTS.md:62`, `AGNOTE4482PHI.t1.md:55-58`). `.spynel/config.yaml:12-15` defines **four** prefix slots — chat, developer, reviewer, heartbeat — and **all four are empty strings today**, so no prefix is actually applied. There is no notification prefix slot. The table records the slot each phase *would* use.

| Phase | Spynel role | Prefix slot | Register row KIND | Make target |
|---|---|---|---|---|
| claim | `agent-developer` | `harness.developer_agent_prefix` | `CLAIM` | `register-claim` (`pmoves/Makefile:395`) |
| work | `agent-developer` | `harness.developer_agent_prefix` | `UPDATE`, or no row | `register-note` (`pmoves/Makefile:437`) |
| sign | **no counterpart** | none | ACK block / trail entry | `sign-trail` (`pmoves/mk/preflight.mk:512`) |
| release | `agent-developer`; `agent-reviewer` when `review_required: true` | developer / reviewer slot | `RELEASE` | `register-release` (`pmoves/Makefile:417`) |

`sign` is the real gap: no Spynel role emits a CHIT signature, and a `completion_summary` is not one. A task can move `working -> done` with no trail entry and no register row at all.

## Two registers, two owners

| Register | Path | Owner | Written by |
|---|---|---|---|
| CHIT claim register | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | PMOVES | `register-claim` / `register-release` / `register-note` (`pmoves/Makefile:389-487`) — never by hand |
| Spynel claim / lease | `.spynel/runtime/leases/` | Spynel | Spynel alone; agents must not edit (`.spynel/AGENTS.md:10`, `:20`) |

**Neither register is derived from the other.** No tool reads across them, no transition in one writes the other, and an open CHIT lane neither blocks nor is blocked by a Spynel dispatch. A Spynel-dispatched developer session that edits code must file its own `CLAIM` row: being claimed into `working/` is task ownership, not lane ownership.
