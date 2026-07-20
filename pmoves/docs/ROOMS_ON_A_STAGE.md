# Rooms on a Stage — Model Overview
_Last updated: 2026-07-07_

## What This Is

PMOVES.AI organizes its platform as rooms on a stage — a topology model with three layers: rooms, stages, and overlays. This document explains the model end-to-end.

## The Three Layers

### Rooms (audience-facing topology)

Rooms are the entrypoints through which users (human or agent) access the platform's capabilities. Each room is an agent-owned workspace with bound services, skills, and notebook state.

| Room | Purpose | Agent | Typical Stage |
|------|---------|-------|--------------|
| **Z890 Infra Fabric** | Topology, service health, secrets, operator bring-up | z890-claude | live |
| **4090 Field Control** | Review, triage, notebook-backed analysis | 4090-claude | live |
| **5090 Voice Studio** | TTS, media pipelines, audition workflows | 5090-claude | live |
| **5090 KiloCode GLM Workstation** | GPU inference specialist, GLM Coding Plan | 5090-kilocode | rehearsal |
| **PMOVES Demo Room** | One-click Agent Zero + 4090 Claude claws + HERMES assist | 4090-claude | rehearsal |
| **HERMES Agent Control** | Cross-platform gateway: profiles, skills, cron, NATS bridge | hermes-agent | rehearsal |
| **Fordham Hill Community** | Cost-pooling mesh + co-op self-governance pilot (onboarding / transaction / creator / voice) | fordham-steward | rehearsal |

_Catalog: `pmoves/config/rooms/catalog.json` (7 rooms). All 4 node rooms typically `live`; demo / hermes / fordham are `rehearsal`._

Planned rooms (from the prospectus frame):
- **foyer** — first P7 screen, room selection
- **review-room** — Graphiti trails, notebooks, approval state
- **voice-room** — Flute/TTS/Pipecat as instrument rack
- **media-room** — beats, Jellyfin, creator publishing, Discord cards
- **war-room** — enterprise, fleet, Hostinger/KVM posture

### Stage (lifecycle state model)

Every room has a stage state that describes its current lifecycle position:

| Stage | Meaning |
|-------|---------|
| `rehearsal` | Setup, testing, configuration — not yet serving production work |
| `live` | Active operation — serving real workloads |
| `review` | Audit, approval, inspection — paused for evaluation |
| `archive` | Completed or dormant — preserved but inactive |

Stage transitions are managed by P7. A room in `rehearsal` should show a rehearsal banner; a room in `live` should show a live indicator.

### Overlays (runtime/persona bindings)

> **Vocabulary change (2026-07-20, open-room lane).** Earlier drafts of this document called these "suits". That term collided with `pmoves/configs/model-suits/` (per-model YAML profiles in the model framework) and caused confusion between runtime/persona overlays and model profiles. Renamed to **overlays** in the room context; "suits" remains the canonical term for per-model profiles under `pmoves/configs/model-suits/`.

Overlays are layered onto rooms — they are NOT the platform itself, they are the visible styling and runtime binding:

- **Base overlay**: upstream Agent Zero (external baseline)
- **Custom overlay**: PMOVES hardened bindings (security, CHIT, NATS wiring)
- **Styling overlay**: voice, theme, persona (visible layer)

A room can switch overlays without changing rooms. Overlay selection is profile-governed, not raw-env governed.

## P7 — The Stage Manager

P7 (Pinokio 7) is the room-aware stage manager. It:
1. Knows which rooms exist (via `pmoves/config/rooms/catalog.json`)
2. Selects the appropriate room profile for a given workload
3. Loads the correct overlay for the room
4. Manages stage transitions (rehearsal -> live -> review -> archive)
5. Provides NATS control plane subjects (`p7.nats.launch`, `p7.nats.session`) for room entry and lifecycle

P7 is not just a process spawner — it is the context that agents launch into.

## What Rooms Own vs. Don't Own

Rooms own:
- Shell theme and layout
- Installed apps and default routes
- Room-local policy decisions
- Bindings between skills and surfaces

Rooms do NOT own:
- Durable memory (that's the notebook plane)
- Cross-room infrastructure (that's the geometry/CHIT fabric)
- Orchestration data planes (that's NATS/observability)

## References

- [Room Manifest Contract](ROOM_MANIFEST_CONTRACT.md) — interface specification
- [AGNOTE4482](AGENTS/AGNOTE4482.md) — P7 stage manager definition (L25-27)
- [P7 Playground — Prospectus Frame](archive/AGNOTE_P7_PLAYGROUND-2026-04-10.md) — rooms/stage/suits model (L338-368)
- [Roadmap W1-W5](AGENTS/AGNOTE4482_ROADMAP_W1-W5.md) — prospectus alignment
- [Signoff Checklist](AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md) — 1.4 coherence gate
- [CnC Architecture](architecture/PMOVES_CnC.md) — P7 as stage manager in command-and-control context

## CHIT Signing-Card Activation Checklist

> **See canonical checklist in [`pmoves/docs/ROOM_MANIFEST_CONTRACT.md`](ROOM_MANIFEST_CONTRACT.md#chit-signing-card-activation-checklist).** That is the single source of truth. This doc links rather than duplicates to prevent drift. Last consolidated: 2026-07-20 (open-room lane; see `AGNOTE4482PHI.t1.md`).
