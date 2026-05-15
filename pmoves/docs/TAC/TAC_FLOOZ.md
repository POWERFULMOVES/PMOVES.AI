# TAC Tree: FlOO$ — Life-Persona-Voice Pipeline

> Technology-Architecture-Context tree for the FlOO$ economic-persona overlay that bridges financial state to prosodic voice rendering. This document is the W6-P5 architecture review per issue #1412.

> **Status:** Architecture-only. Per Village Rule, no runtime code lands until signoff on §1 and §7 of `AGNOTE4482_SIGNOFF_CHECKLIST.md`.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | FlOO$ (life-persona-voice overlay) |
| **Port** | TBD — Phase A health endpoint (`FLOOZ_PORT`, suggested `8119` to sit between Evo Controller `8113` and A2UI bridge `9224`) |
| **Health** | `GET /healthz` (3-tier: healthy/degraded/unhealthy, modeled on `wger/observability/views.py`) |
| **Metrics** | `GET /metrics` (Prometheus; gated by `EXPOSE_PROMETHEUS_METRICS`) |
| **Submodule** | Lives in `pmoves/services/flooz/` (in-tree, sibling to `pmoves/services/common/`) |
| **Docker Profile** | `flooz`, `persona` |
| **Tier** | api |
| **Class** | Specialized — Adaptation pore (L4 of Grand Convergence) |
| **Evolution** | Stage 0 (architecture only) |

## Architecture Position

FlOO$ is a thin **overlay service**, not a primary pipeline stage. It listens for financial-state events, computes a persona-overlay envelope, and emits an extended CGP packet that ToKenism's existing prosodic pipeline consumes unchanged. It owns no audio synthesis and no economic-data storage of its own.

```
Wealth (Firefly III)  ─┐
Health (wger)         ─┼─→  finance.event.v1  ─→  FlOO$ Persona Mapper  ─→  flooz.cgp.ready.v1
Agent-Zero finance-skill ┘                       (state machine)              (CGP v0.2 + persona overlay)
                                                                                       │
                                                                                       ▼
                                                                  tokenism.prosodic.bpm.v1
                                                                  (ToKenism merges overlay + BPM profile)
                                                                                       │
                                                                                       ▼
                                                              POST /v1/voice/synthesize/prosodic
                                                                       (Flute-Gateway)
                                                                                       │
                                                                                       ▼
                                                                       audio (per persona register)
```

**Confirmed against:**
- `pmoves/tools/beats_to_voice.py:65` — `NATS_SUBJECT = "tokenism.prosodic.bpm.v1"` is the ToKenism inbound subject FlOO$'s output must conform to.
- `pmoves/tools/bpm_encoder.py:404-485` — `build_cgp_packet()` produces the CGP v0.2 shape FlOO$ extends.
- `pmoves/.claude/context/nats-subjects.md` — no `finance.*`, `flooz.*`, or `wealth.*` subjects currently registered; all four below are net-new and must be added in Phase A.

## NATS Subjects (Proposed)

| Subject | Direction | Producer → Consumer |
|---------|-----------|----------------------|
| `finance.event.v1` | ingress | Wealth / Health / agent-finance-skill → FlOO$ |
| `flooz.persona.computed.v1` | egress (audit) | FlOO$ → any observer (Hyperdimensions, audit log) |
| `flooz.cgp.ready.v1` | egress (control) | FlOO$ → ToKenism (alternative to direct `tokenism.prosodic.bpm.v1` write — preserves FlOO$ vs ToKenism separation) |
| `flooz.persona.cache.invalidate.v1` | sideband | Operator / signoff event → FlOO$ |

**Disambiguation against the MiniMax Phase 2 catalog (PR #1484):** MiniMax adds `minimax.character.*` and `minimax.voice.prosodic.v1` for **character-archetype** synthesis (Dr. Bean / Mr. Clean / PowerPuff Girls). FlOO$ adds `flooz.*` for **economic-state** persona overlays. They are orthogonal and chain — FlOO$ outputs an overlay that names which MiniMax character to render; MiniMax renders the audio. No subject collision.

**Payload schema for `finance.event.v1`:**
```json
{
  "user_id": "pmoves-user-uuid",
  "event_type": "income|debt|recurring|surplus|deficit|asset_change",
  "amount": 1500.00,
  "currency": "USD",
  "delta_period": "instantaneous|weekly|monthly",
  "source": "firefly|wger_subscription|manual|agent_inference",
  "timestamp": "2026-05-15T22:00:00Z"
}
```

**Payload schema for `flooz.persona.computed.v1`** (audit-shaped, derivable from a `finance.event.v1`):
```json
{
  "user_id": "pmoves-user-uuid",
  "trigger_event_id": "finance-event-uuid",
  "persona": {
    "economic_state": "buoyant|stable|constrained|distressed",
    "register": "elevated|measured|reduced|whispered",
    "archetype_hint": "dr-bean|mr-clean|powerpuff-girls",
    "confidence": 0.83
  },
  "ttl_seconds": 1800,
  "timestamp": "2026-05-15T22:00:00Z"
}
```

## CHIT Integration — CGP Packet Extensions

FlOO$'s extension to the CGP v0.2 packet produced by `bpm_encoder.build_cgp_packet()` is **additive**: it adds one new top-level key, `persona_overlay`, leaving every existing key (`spec`, `type`, `id`, `super_nodes`, `control_plane`, `state_vector`) untouched. ToKenism consumers that don't understand the overlay simply ignore it — the pipeline degrades gracefully to today's behavior.

```jsonc
{
  "spec":   "chit.cgp.v0.2",                    // unchanged
  "type":   "tokenism.prosodic.bpm.v1",         // unchanged
  "source": "flooz",                            // overrides bpm_encoder's "4090-claude" when FlOO$ is the producer
  // ... super_nodes[], control_plane unchanged ...

  "persona_overlay": {                          // NEW — FlOO$'s contribution
    "version": "0.1",
    "economic_state": "stable",
    "register": "measured",
    "archetype_hint": "dr-bean",
    "modulation": {
      "bpm_bias":      -10,      // signed offset applied to chunk-level BPM (clamped to 40..200)
      "freq_bias":     -0.05,    // signed offset applied to control_plane.state_vector.Hz (normalized)
      "kappa_bias":    -0.10,    // signed offset applied to pause weight (more weight = more pauses)
      "temperature_bias": -0.05  // signed offset applied to control_plane.param_surface.temperature
    },
    "trigger_event_id": "finance-event-uuid",
    "ttl_seconds": 1800
  }
}
```

**Invariants:**
1. `persona_overlay.modulation.*_bias` values are bounded `[-0.5, +0.5]` per field to prevent runaway prosody.
2. After ToKenism applies the biases, final clamped ranges are: BPM `[40, 200]`, freq-normalized `[0.0, 1.0]`, kappa `[-1.0, 0.0]`, temperature `[0.1, 1.5]`.
3. If `persona_overlay.ttl_seconds` has expired by the time ToKenism receives the packet, the overlay is dropped and the base packet plays unmodified (degraded mode).
4. `persona_overlay.confidence` (from `flooz.persona.computed.v1`) is folded into the CGP `super_nodes[0].constellations[0].points[*].conf` — already a [0,1] range.

## Persona State Model

FlOO$ runs a small deterministic state machine — **not** an LLM call per event. Throughput target is sub-50ms per `finance.event.v1` so the pipeline doesn't add audible lag.

| Input event | Computed economic_state | Register | Archetype hint | Modulation envelope |
|-------------|------------------------|----------|----------------|---------------------|
| Income > 30-day avg × 1.5 | `buoyant` | `elevated` | `powerpuff-girls` | bpm_bias +12, freq +0.08, kappa +0.05, temp +0.10 |
| Income within ±1.5σ of 30-day avg | `stable` | `measured` | `dr-bean` | (zero modulation — passthrough) |
| Debt or recurring obligation triggered | `constrained` | `reduced` | `mr-clean` | bpm_bias −10, freq −0.05, kappa −0.10, temp −0.05 |
| Sustained deficit (rolling 7-day) | `distressed` | `whispered` | `dr-bean` | bpm_bias −20, freq −0.10, kappa −0.20, temp −0.15 |

**State transitions:** monotonic by event severity (deficit > constrained > stable > buoyant) with a configurable hysteresis window (default 2 events) to prevent register oscillation. The state machine is the small testable surface — Phase B target is 100% branch coverage in pytest.

**Reference parameter space:**
- `pmoves/tools/bpm_encoder.py:57-72` — `BOUNDARY_BPM` and `BOUNDARY_PAUSE_MS` constants define the unmodulated baseline FlOO$ biases against.
- `pmoves/tools/bpm_encoder.py:76-82` — `TEMPO_LABELS` (Largo/Andante/Moderato/Allegro/Presto) provide human-readable register labels for the audit subject.

## MOF Lattice Alignment

Per `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md`: every PMOVES node is a pore in the lattice. FlOO$ is positioned as a **small-aperture adaptation pore** sitting on the L4 (Adaptation) plane of the Grand Convergence 5-layer model.

| MOF property | FlOO$ value |
|--------------|-------------|
| **Capacity class** | Specialized (one well-typed function: state → overlay) |
| **Throughput target** | ≥ 200 events/s on a single replica (state-machine, no I/O blocking) |
| **Neighbor pores (upstream)** | Wealth (Firefly), Health (wger), Agent-Zero finance-skill |
| **Neighbor pores (downstream)** | ToKenism (canonical), Hyperdimensions (audit/visualization) |
| **Adsorbs** | Financial-state events (small payloads, high frequency) |
| **Emits** | Persona overlays (small payloads, lower frequency due to TTL coalescing) |
| **Backpressure model** | Drop-newest if queue > 1000 (loud audio register can be re-derived from the next event) |
| **L4 fit** | Yes — FlOO$ is pure adaptation: it changes how an agent *sounds*, not what an agent *does* |
| **L5 fit** | Indirect — economic state is the input, but FlOO$ doesn't transact; that stays in Wealth/Firefly |

## Phase A — Foundation (P0)

**Goal:** FlOO$ exists as a registered, observable service, with NATS plumbing wired, but its state machine returns a zero-modulation (passthrough) overlay for every event.

| Deliverable | File / Surface |
|-------------|----------------|
| Service skeleton | `pmoves/services/flooz/main.py` (FastAPI on `:8119`) |
| Health endpoint | `GET /healthz` — 3-tier model, returns `degraded` when NATS disconnected |
| Metrics endpoint | `GET /metrics` — Prometheus, counters for `flooz_events_total`, `flooz_overlays_emitted_total`, `flooz_persona_state_total{state=...}` |
| NATS subjects registered | Add four `flooz.*` subjects + `finance.event.v1` to `pmoves/.claude/context/nats-subjects.md` |
| Docker wiring | `docker-compose.yml` block under `flooz` profile, `*tier-api-hardened` anchor |
| Prometheus scrape | `pmoves/monitoring/prometheus/prometheus.yml` adds `flooz` job |
| Agent signature | `pmoves/config/agent_signatures.yaml` adds `flooz` agent_id |
| Unit tests | `tests/services/flooz/test_passthrough.py` — input event → CGP packet with empty `persona_overlay.modulation` (all zero biases), but valid `version` and `trigger_event_id` |

**Acceptance:** A `finance.event.v1` published from a smoke test arrives at ToKenism via `flooz.cgp.ready.v1` with a valid CGP v0.2 packet whose `persona_overlay.modulation.*_bias` values are all `0.0`. ToKenism renders identically to the no-FlOO$ baseline.

## Phase B — Persona Engine (P1)

**Goal:** State machine implemented + tested. FlOO$ actually modulates.

| Deliverable | File / Surface |
|-------------|----------------|
| State machine | `pmoves/services/flooz/state_machine.py` — deterministic, no I/O |
| Hysteresis window config | env: `FLOOZ_HYSTERESIS_EVENTS=2` |
| Modulation envelope constants | `pmoves/services/flooz/envelopes.py` — the table in §Persona State Model above |
| TTL coalescing | per-user persona cache with TTL, invalidated by `flooz.persona.cache.invalidate.v1` |
| Unit tests | `tests/services/flooz/test_state_machine.py` — 100% branch coverage on the 4×N transition matrix |

**Acceptance:** Replay a recorded sequence of 50 `finance.event.v1` events; assert the emitted overlay sequence matches a known-good fixture file at `tests/services/flooz/fixtures/seq_2026-05-15_baseline.json`.

## Phase C — Voice Alignment (P2)

**Goal:** End-to-end smoke through Flute-Gateway, confirming the overlay actually changes audible output.

| Deliverable | Description |
|-------------|-------------|
| ToKenism overlay-aware merge | ToKenism reads `persona_overlay.modulation` and applies biases before calling Flute. (May already be a one-line patch in `beats_to_voice.py` Stage 3.) |
| Flute integration smoke | `make -C pmoves flooz-smoke` — publishes 4 events (one per economic_state), captures 4 audio files, runs a coarse spectral check to confirm bpm/Hz delta is non-zero between adjacent states. |
| MiniMax archetype handoff | When `persona_overlay.archetype_hint` is non-null, Flute routes to the corresponding MiniMax character voice (see PR #1484 — `minimax.character.request.v1`). |
| Cross-node validation | 4090-CLAUDE confirms persona selector + botz_cli interop; SPARK confirms hologram-geometry overlay rendering matches state transitions. |

**Acceptance:** §7 (persona-voice alignment) of `AGNOTE4482_SIGNOFF_CHECKLIST.md` flips from open to closed with a captured audio diff demonstrating audible state-driven modulation.

## CHIT Integration Status

| Capability | Status (post-Phase A) | Status (post-Phase C) |
|------------|----------------------|----------------------|
| CGP packet generation | Passthrough (zero modulation) | Active with `persona_overlay` block |
| Delta sensitivity | `false` | `true` (bpm_bias modulates `state_vector.delta`) |
| Hz sensitivity | `false` | `true` (freq_bias modulates `state_vector.Hz`) |
| Swarm participant | No | Optional — observer-only on `flooz.persona.computed.v1` |
| Attribution gated | No | Yes — overlay tagged `source: "flooz"` for audit |
| BPM capable | No (consumer of bpm_encoder, not producer) | Same |

## Production Audit Checklist (Targets)

| Requirement | Phase A target | Notes |
|-------------|---------------|-------|
| `/healthz` endpoint | GREEN | 3-tier, NATS-disconnected → degraded |
| `/metrics` endpoint | GREEN | Prometheus format |
| Auth | N/A | Internal NATS-only service; no public HTTP except `/healthz` + `/metrics` |
| Docker hardening | GREEN | `*tier-api-hardened` |
| NATS integration | GREEN | 4 subjects registered, healthcheck includes NATS reachability |
| `env.shared` format | GREEN | All config via env vars, no hardcoded credentials |
| Prometheus scrape | GREEN | `flooz` job in `pmoves/monitoring/prometheus/prometheus.yml` |

## Cross-Links

- **Issue:** [#1412](https://github.com/POWERFULMOVES/PMOVES.AI/issues/1412)
- **Signoff:** [`AGNOTE4482_SIGNOFF_CHECKLIST.md`](../AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md) §1 (architecture), §7 (persona-voice alignment)
- **Roadmap:** [`AGNOTE4482_ROADMAP_W1-W5.md`](../AGENTS/AGNOTE4482_ROADMAP_W1-W5.md) W6-P5 row
- **Upstream services:** [`TAC_WEALTH.md`](./TAC_WEALTH.md), [`TAC_HEALTH.md`](./TAC_HEALTH.md)
- **Downstream services:** ToKenism (no TAC yet — flagged below), [`TAC_FLUTE.md`](./TAC_FLUTE.md) if present
- **Adjacent persona work:** PR #1484 (MiniMax Token Plan Phase 2 — character archetypes)
- **Architecture thesis:** [`PMOVES_MOF_ARCHITECTURE.md`](../architecture/PMOVES_MOF_ARCHITECTURE.md), [`PMOVES_GRAND_CONVERGENCE.md`](../architecture/PMOVES_GRAND_CONVERGENCE.md)
- **CGP reference:** `pmoves/tools/bpm_encoder.py:404-485` (`build_cgp_packet`)

## Open Items (post-architecture, pre-code)

1. **Reviewer signoff** — 4090-CLAUDE (downstream voice integration), SPARK (hologram-geometry overlay), DARKXSIDE (operator approval on subject names + `flooz` agent_id + economic_state taxonomy).
2. **`TAC_TOKENISM.md` gap** — ToKenism has no TAC tree; FlOO$'s downstream contract relies on undocumented behavior. Worth a separate issue.
3. **Subscription privacy** — `finance.event.v1` payloads carry user financial data on the NATS bus. Phase A must decide: (a) bus is internal-only, accept clear payloads, or (b) wrap in CHIT envelope for at-rest encryption.
4. **MiniMax-edition handoff contract** — define the exact field in `persona_overlay.archetype_hint` ↔ `minimax.character.request.v1.persona` mapping. Drafted here but unverified against the MiniMax PR #1484 payload schema.
5. **Operator data flow** — how does Wealth/Firefly actually emit `finance.event.v1`? Phase A may need a small adapter sidecar if Firefly doesn't speak NATS natively (it doesn't, as of last audit).
6. **W6-P3 (Voice binding) intersection** — that lane (5090-claude, READY) needs to verify with live Flute. FlOO$ Phase C depends on W6-P3 closing. Sequencing: W6-P3 verification → FlOO$ Phase A → FlOO$ Phase B → FlOO$ Phase C.

## Emperor-CHIT-Humility Disclosure

**Have (verified in this session):** CGP v0.2 packet shape from `bpm_encoder.py:404`; ToKenism inbound subject `tokenism.prosodic.bpm.v1` from `beats_to_voice.py:65`; BPM parameter space + tempo labels; MiniMax character archetype payload schema from PR #1484; no `finance.*` or `flooz.*` subjects currently in `nats-subjects.md`; no FlOO$ prior art in `pmoves/docs/`.

**Missing (flagged in §Open Items):** ToKenism overlay-merge code location (assumed to be a one-line patch in `beats_to_voice.py` Stage 3 — needs grep when Phase C starts); Firefly III event emission path; production economic-state taxonomy from DARKXSIDE (the four-state model proposed here is my draft, not approved).

<!-- GRAPHITI_MARK: 5090-CLAUDE::W6-P5-FLOOZ-ARCH-REVIEW::2026-05-15 -->
