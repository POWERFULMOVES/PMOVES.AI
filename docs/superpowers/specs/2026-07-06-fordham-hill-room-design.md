# Fordham Hill Room — Design Spec

_Date: 2026-07-06 · Status: approved design, pre-fan-out · Owner: DARKXSIDE (sole operator)_

## Purpose

Elevate the Fordham Hill pilot from a set of tools + docs into a first-class PMOVES
**room** with a **dedicated agent team** that runs the pilot end-to-end: onboard residents,
keep the community books, create pilot materials, and *speak* to residents (voice-first).
The room's public face is the CF dev site; its private live surface is the tailnet dashboard
already deployed. Launch is **readiness-driven, not date-driven** (Dec 19 → Cinco both
slipped by circumstance; readiness criteria below are the gate).

## Grounding (existing patterns this conforms to)

- Rooms: `pmoves/config/rooms/catalog.json` (schema `{room_id, agent_id, alter, display_name,
  manifest, summary}`, 5 rooms today) + a manifest per `pmoves/docs/ROOM_MANIFEST_CONTRACT.md`.
- Agents/teams: `pmoves/configs/agent-teams.yaml` (10 teams) + `pmoves/config/agent_signatures.yaml`
  + persona docs. Minted via the Archon pattern (`archon:mint-agent`).
- CF site: `make pmoves-ai-deploy` (Cloudflare Pages).
- Pilot surface (live): `https://pmoves-kvm4-1.tailcad9b4.ts.net/` (tailnet-only dashboard).
- Verification/economics: `pmoves/docs/pilots/fordham-hill/` (docs 01–06).

## The room

`fordham-hill.room.ops` — "Fordham Hill Community Pilot". Lead alter `fordham-ops`,
lead agent `fordham-lead`. Manifest `fordham-hill.room.ops.json` binds:
- **surface:** the tailnet resident dashboard (view) + the CF public page (recruit).
- **skills:** `mesh-egress-ab`, `pmoves-chit-sign` (vote/receipt identity), Wealth/Firefly,
  `persona-bind` (voice), `tts:*`/`voice:*`.
- **notebook state:** pilot roster + ledger refs + observation snapshots.

## Dedicated agent roster (new `fordham-pilot` team)

| Agent | Responsibility | Node | Ties |
|-------|----------------|------|------|
| `fordham-onboarding` | resident intake → issue signing card (= vote identity) → add to `users.yaml` roll → bump dashboard `HOMES` in `pilot.conf` | z890 | governance `vote.signed.v1`, `sign_cgp()` |
| `fordham-transaction` | load contributions/expenses to PMOVES-Wealth via Firefly `POST /api/v1/transactions`; reconcile per verification pipeline (doc 05) | z890 | Wealth, DoX, doc 05 |
| `fordham-creator` | pilot materials — explainers, flyers, dashboard/site copy, social | 5090 | PMOVES-Creator, `.kilo` briefs |
| `fordham-voice` | **speak** to residents — voice-first onboarding + dashboard narration, persona-bound | 5090 | Flute/TTS, `persona-bind`, launch personas |

Each agent = a persona doc + `agent_signatures.yaml` entry + `agent-teams.yaml` `fordham-pilot`
membership + room binding. **Scaffolded as files by the fan-out (no Archon needed); the live
Archon mint (register + `archon.mint.agent.v1`) is a separate activation step requiring Archon up.**

## Connections (fanned lanes, stubbed → wired)

- **CF dev site** — a **public** `fordham-hill` recruiting page on the pmoves-ai CF site
  (value prop + "join", NOT the private live numbers). Deliberately separate from the tailnet
  dashboard: public = pitch, tailnet = real ops. Coordinated with **5090's in-flight site update**
  via `.kilo/command/` briefs so 5090/KiloCode picks up creator + site work without collision.
- **5090 handoff** — `.kilo/command/fordham-*.md` briefs (Three-Body: Claude analyzes → KiloCode
  GLM implements → trail signed) for the creator + voice + site work that lives on 5090.
- **Launch readiness (not a date)** — the room ships when the readiness criteria below are met.

## Launch readiness criteria (the gate)

1. Room + 4 agent artifacts scaffolded and bound; Archon up; agents minted + registered.
2. Dashboard live on ≥2 hubs (kvm4-1 + kvm4-2 failover) with real `HOMES` from enrollment.
3. Onboarding path proven end-to-end for ≥1 real household (card issued, roll updated, dashboard reflects).
4. Wealth ledger loads + reconciles ≥1 real document (verification pipeline doc 05 golden test passes).
5. Voice agent can speak the dashboard state + an onboarding prompt (persona-bound).
6. CF public page live; governance scaffold routed to counsel.

## Archon prerequisite (corrected topology)

Archon is **not** a single central service. Archon + Agent Zero run as a **distributed duo** —
paired, per-node / per-node-pair (e.g. 5090↔Z890, SPARK↔Knuckles), Agent Zero as "Galvatron"
to Archon's "Psychronus". There is not one Archon just as there is not one Agent Zero.

For the Fordham mint, **this node (4090) runs its own Agent-Zero + Archon duo** — no central
host decision. Bring-up on 4090: the Agent-Zero + Archon duo (Supabase-backed) via the agents
compose (`make -C pmoves up-archon-submodule` + `archon-db-setup`, with Agent Zero as the duo
partner). Gates the live mint-activation only; artifact scaffolding does not need it.

## Fan-out lanes (once approved)

1. **Room def** — `catalog.json` entry + `fordham-hill.room.ops.json` manifest (per contract).
2. **Agent roster** — 4 persona docs + `agent-teams.yaml` `fordham-pilot` team + `agent_signatures` + room bindings.
3. **CF public page** — `fordham-hill` recruiting page + deploy wiring (`make pmoves-ai-deploy`).
4. **5090 `.kilo` briefs** — creator + voice + site handoff briefs.
5. **Launch-readiness doc** — the criteria above as a tracked checklist.
6. **Synthesis + wiring map** — how the pieces connect; the Archon-up + mint activation runbook.

Each lane grounds in the real repo, cites files, and is adversarially checked. Governance/legal
items stay DRAFT — REQUIRES LEGAL REVIEW; fraud investigation stays human-led (PMOVES-mike + Missing Link).

## Testing / verification

- Room manifest validates against the contract (parity check like `rooms.ts`).
- Agent artifacts pass the schema/registry checks (`agent_signatures` valid, team membership resolves).
- CF page deploys + loads publicly; tailnet dashboard stays private (no cross-leak).
- Readiness checklist items are each independently verifiable (evidence, not assertion).
