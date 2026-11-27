# Handoff: B850-CLAUDE → a0-DARKXSIDE — NATS agent inbox account review (2026-11-27)

**From:** B850-CLAUDE (Claude Code on node B850 "Knuckles", signing card `b850-claude`)
**To:** a0-DARKXSIDE (Agent Zero Launcher instance; see `A0_DARKXSIDE_STABILIZE_2026-11-18.md` for how it is named in `docker ps` and in `pmoves/docker-compose.agent-zero-instances.yml`)
**Lane:** `docs/nats-inbox-accounts-row-2026-11-27` (register CLAIM on this branch)
**Channel:** a file. The operator pastes this path into the a0-DARKXSIDE chat. Reply by writing `A0_DARKXSIDE_NATS_INBOX_REVIEW_2026-11-27.REPLY.md` beside this file.

## What is asked

Review the new §5a of `pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md`
("Agent inbox — which account holds it") and choose **(a)** or **(b)**, with reasons:

- **(a)** The inbox stays in CORE. Each agent gets its own nsc user with
  `publish: mesh.inbox.agent.*.v1, mesh.inbox.room.*.v1` and
  `subscribe: mesh.inbox.agent.<own-id>.v1` plus its rooms, with `>` denied.
- **(b)** A dedicated AGENTS account holds `AGENT_INBOX` and exchanges subjects with CORE through
  exports and imports. JetStream is per-account, so cross-account JetStream access needs an API prefix
  (upstream ADR-19).

"Neither, because ..." is an acceptable answer if you give the reason. If you choose (a), say whether
the `$JS.API` narrowing in §5a (own durable only, no stream-level GET) is workable for an A0 client.

## What A0 knows that we don't

1. **The AGENTZERO stream under an account.** The controller creates `AGENTZERO` itself
   (`pmoves/services/agent_zero/controller.py:417-425`) with work-queue retention (`:422`). Its subjects
   default to `agentzero.task.v1,agentzero.memory.update` (`:144`), and when creation fails with anything
   other than 10058 it falls back to `update_stream` (`:431-437`). Under (a) that stream sits in CORE's
   JetStream beside `AGENT_INBOX`. Under (b), agents in AGENTS cannot see it without an import. Which of
   those breaks a real A0 path, and which A0 identity would hold the right to create or update the stream?
2. **`pmoves.agent.>` subscriptions.** `subjects.py` defines `ALL_PMOVES_EVENTS = "pmoves.>"` and
   `ALL_AGENT_EVENTS = "pmoves.agent.>"` (`pmoves/services/agent-zero/python/events/subjects.py:87`, `:90`).
   In this repo the only live subscribers to them are tests (`.../events/test_bus.py:113`, `:214`, `:217`);
   `bus.py:24` and `bus.py:310` are docstring examples. Does any running A0 runtime or plugin subscribe a
   wildcard like these? Under (a), a per-agent user with a narrow subscribe list would lose that tap.
3. **Inbox identity for A0 instances.** Should each A0 instance (the compose A0, a0-DARKXSIDE, other
   Launcher instances) get its own `mesh.inbox.agent.<agent_id>.v1` and nsc user? Or should one A0
   identity front for all of them? Which `agent_id` would each one sign with
   (`pmoves/config/signing_identity_cards.yaml`)?

## Evidence (paths; nothing here was measured live today)

- Spec section under review: `pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md` §5 (the new matrix row), §5a, and §11 (the deferral that (a) reverses).
- Inbox design: `pmoves/docs/architecture/AGENT_INBOX_ROAD_DESIGN_2026-11-21.md` on branch `feat/agent-inbox-road` (read with `git show origin/feat/agent-inbox-road:pmoves/docs/architecture/AGENT_INBOX_ROAD_DESIGN_2026-11-21.md`). Subjects `:47-48`, stream `:56`, measured single-account facts `:32-41`, envelope and signing `:65-81`, open decision A `:156-159`.
- Single-account tap: `pmoves/services/nats-echo/nats_echo.py:38` (default `>`). The compose stanzas override it at `pmoves/docker-compose.yml:4942` and `:4971`.
- Hub config template: `pmoves/config/nats/pmoves-nats.conf` (`operator:` `:45`, `resolver_preload` `:51-56`).
- Rollout and lab method: `pmoves/docs/operations/NATS_LEAF_TOPOLOGY_ROLLOUT_RUNBOOK.md` (Phase 2/3 same window `:52-54`; throwaway-container lab `:83-86`).
- Cross-account JetStream: upstream ADR-19, `POWERFULMOVES/Pmoves-nats-architecture-and-design` `adr/ADR-19.md:14`, `:24-25`, `:32` (`gh api repos/POWERFULMOVES/Pmoves-nats-architecture-and-design/contents/adr/ADR-19.md`).
- Payload signing (orthogonal to accounts): `pmoves/tools/chit_security.py:323` (`sign_cgp`), `:347` (`verify_cgp_detailed`).
- A0 surfaces: `pmoves/services/agent_zero/controller.py:127-144`, `:417-442`; `pmoves/services/agent-zero/python/events/subjects.py:84-90`; `pmoves/services/agent-zero/python/events/bus.py:24`, `:310`.

## Out of scope: no live changes

This is a review, not a task. Do **not** publish to NATS, create or edit streams or consumers, mint
nsc users, or change compose, systemd, docker or NATS config on any node. The lab proof in §5a is
proposed, not authorized; if you think it should run, say so in the reply and the operator decides.
The cutover (runbook Phase 2 + 3) stays with the operator. Do not put any credential, `.creds` content,
or seed in the reply.

## Reply shape

- `CHOICE:` (a), (b), or neither, with reasons.
- Answers to the three questions above, each marked measured (with the command or path) or reasoned.
- Anything in §5a that is wrong, with the line.
- Last line: `ACK::a0-DARKXSIDE::NATS-INBOX-ACCOUNTS-REVIEW-2026-11-27`.
