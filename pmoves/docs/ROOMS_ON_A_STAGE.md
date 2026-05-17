# Rooms on a Stage — Model Overview
_Last updated: 2026-05-17_

## What This Is

PMOVES.AI organizes its platform as rooms on a stage — a topology model with three layers: rooms, stages, and suits. This document explains the model end-to-end.

## The Three Layers

### Rooms (audience-facing topology)

Rooms are the entrypoints through which users (human or agent) access the platform's capabilities. Each room is an agent-owned workspace with bound services, skills, and notebook state.

| Room | Purpose | Agent | Typical Stage |
|------|---------|-------|--------------|
| **Z890 Infra Fabric** | Topology, service health, secrets, operator bring-up | z890-claude | live |
| **4090 Field Control** | Review, triage, notebook-backed analysis | 4090-claude | live |
| **5090 Voice Studio** | TTS, media pipelines, audition workflows | 5090-claude | live |
| **5090 KiloCode GLM Workstation** | GPU inference specialist, GLM Coding Plan | 5090-kilocode | rehearsal |

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

### Suits (runtime/persona bindings)

Suits are layered onto rooms — they are NOT the platform itself, they are the visible styling and runtime binding:

- **Base suit**: upstream Agent Zero (external baseline)
- **Custom suit**: PMOVES hardened overlays (security, CHIT, NATS wiring)
- **Styling suit**: voice, theme, persona (visible layer)

A room can switch suits without changing rooms. Suit selection is profile-governed, not raw-env governed.

## P7 — The Stage Manager

P7 (Pinokio 7) is the room-aware stage manager. It:
1. Knows which rooms exist (via `pmoves/config/rooms/catalog.json`)
2. Selects the appropriate room profile for a given workload
3. Loads the correct suit for the room
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
- [P7 Playground — Prospectus Frame](AGENTS/AGNOTE_P7_PLAYGROUND.md) — rooms/stage/suits model (L338-368)
- [Roadmap W1-W5](AGENTS/AGNOTE4482_ROADMAP_W1-W5.md) — prospectus alignment
- [Signoff Checklist](AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md) — 1.4 coherence gate
- [CnC Architecture](architecture/PMOVES_CnC.md) — P7 as stage manager in command-and-control context
