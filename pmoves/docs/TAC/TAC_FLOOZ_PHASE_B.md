# TAC Tree: FlOO$ — Phase B Persona Engine Implementation Spec

> Deep-spec sibling doc to [`TAC_FLOOZ.md`](./TAC_FLOOZ.md). Phase A landed via PR #1487 (architecture-only). This doc specifies *how* Phase B (persona-engine code lane) is built: state-machine API, hysteresis algorithm, TTL coalescing semantics, modulation-envelope code binding, fixture format, operator config envelope, and acceptance gates. Doc-only deliverable per Village Rule. Phase B runtime code lands in a follow-on PR after §1 + §7 signoff per `AGNOTE4482_SIGNOFF_CHECKLIST.md`.

> **Status:** Implementation spec. No runtime code in this PR.

## Scope (this doc only)

| In | Out |
|----|-----|
| State-machine API surface (function signatures, dataclasses) | Phase A architecture (already in `TAC_FLOOZ.md`) |
| Hysteresis algorithm semantics + edge cases | Phase C ToKenism overlay-merge implementation |
| TTL coalescing — cache key, eviction, invalidation flow | Wealth/Firefly adapter sidecar (Phase A scope, separate issue) |
| Modulation envelope constants — bound to `bpm_encoder` baselines | Audio diff acceptance tooling (Phase C scope) |
| Fixture format for 50-event replay acceptance | MiniMax handoff schema validation (Phase C scope) |
| Operator config envelope — env vars, defaults, override patterns | Subscription-privacy CHIT-envelope decision (Phase A scope, separate issue) |
| Open questions for SPARK / 4090 / DARKXSIDE | Persona-mint via Archon (separate cycle, Lane G in MCP-Toolkit plan) |

## State Machine API

The state machine is a **pure function** of (event, recent-event-window, prior-state) → (new-state, overlay). No I/O. No NATS. No clocks beyond the timestamps the input events carry. This is what makes 100% branch-coverage tractable and the throughput target (≥ 200 events/s) achievable.

### Dataclasses

```python
# pmoves/services/flooz/types.py — proposed (Phase B will create)
from dataclasses import dataclass, field
from typing import Literal, Optional

EconomicState = Literal["buoyant", "stable", "constrained", "distressed"]
Register      = Literal["elevated", "measured", "reduced", "whispered"]
ArchetypeHint = Literal["dr-bean", "mr-clean", "powerpuff-girls"]
EventType     = Literal["income", "debt", "recurring", "surplus", "deficit", "asset_change"]

@dataclass(frozen=True)
class FinanceEvent:
    """Mirrors `finance.event.v1` NATS payload (TAC_FLOOZ.md §NATS Subjects)."""
    user_id:       str
    event_type:    EventType
    amount:        float           # always positive; sign carried in event_type
    currency:      str             # ISO 4217; FlOO$ operates currency-agnostic in Phase B
    delta_period:  Literal["instantaneous", "weekly", "monthly"]
    source:        Literal["firefly", "wger_subscription", "manual", "agent_inference"]
    timestamp:     str             # ISO-8601 UTC; matches `finance.event.v1` canonical field (TAC_FLOOZ.md §NATS Subjects). Parsed once at ingress, never re-parsed in hot path.
    event_id:      str             # uuid4 — also used as `persona_overlay.trigger_event_id`

@dataclass(frozen=True)
class ModulationEnvelope:
    """Signed biases applied additively by ToKenism to base CGP packet values.
    All fields bounded [-0.5, +0.5] per the §CHIT Integration invariant in TAC_FLOOZ.md."""
    bpm_bias:         float = 0.0  # added to chunk-level BPM (clamped to BOUNDARY_BPM range)
    freq_bias:        float = 0.0  # added to control_plane.state_vector.Hz (normalized)
    kappa_bias:       float = 0.0  # added to pause weight (-1..0; lower = more pause)
    temperature_bias: float = 0.0  # added to control_plane.param_surface.temperature

@dataclass(frozen=True)
class PersonaState:
    """Computed by the state machine; serialized as `persona_overlay` block in CGP."""
    economic_state:   EconomicState
    register:         Register
    archetype_hint:   ArchetypeHint
    modulation:       ModulationEnvelope
    confidence:       float           # [0.0, 1.0]
    trigger_event_id: str             # FinanceEvent.event_id of the event that caused this state
    ttl_seconds:      int = 1800      # default 30 min; configurable per state via envelopes.py
    version:          str = "0.1"     # persona_overlay schema version

@dataclass
class UserPersonaContext:
    """Per-user rolling context. Lives in the TTL cache (see §TTL Coalescing).
    Mutable — but only the cache layer mutates it under a per-user lock."""
    user_id:                str
    current_state:          PersonaState
    last_n_events:          list[FinanceEvent] = field(default_factory=list)   # bounded ring, see HYSTERESIS_WINDOW
    consecutive_same_state: int = 0                                            # for hysteresis short-circuit
    last_update_unix:       float = 0.0
```

### Core function

```python
# pmoves/services/flooz/state_machine.py — proposed (Phase B will create)
from .types import FinanceEvent, PersonaState, UserPersonaContext
from .envelopes import ENVELOPE_TABLE, classify_event, HYSTERESIS_WINDOW

def step(ctx: UserPersonaContext, event: FinanceEvent) -> tuple[UserPersonaContext, PersonaState]:
    """Pure state-machine step. No I/O.

    Returns:
        (updated_ctx, new_persona_state)

    The updated_ctx is what the cache layer writes back. The returned PersonaState
    is what the publisher serializes into the CGP packet's `persona_overlay` block.
    """
```

The signature is **deliberately tuple-return** rather than mutating-in-place so the cache layer owns mutation under its lock, and the state-machine module remains a pure dependency that the test suite can exercise without any fixtures beyond constructed dataclasses.

### Test seam

```python
# tests/services/flooz/test_state_machine.py — proposed
def test_passthrough_stable_returns_zero_modulation():
    """Income within ±1.5σ of 30-day avg → stable / measured / dr-bean / zero modulation."""

def test_buoyant_transition_above_threshold():
    """Income > 30d_avg * 1.5 → buoyant; envelope matches ENVELOPE_TABLE['buoyant']."""

def test_hysteresis_prevents_single_event_oscillation():
    """One off-trend event after N stable events does NOT flip register if N >= HYSTERESIS_WINDOW."""

def test_sustained_deficit_rolling_window():
    """7 deficit events in rolling 7-day window → distressed (most aggressive modulation)."""

def test_event_severity_monotonicity():
    """deficit > constrained > stable > buoyant — verify no skipped transitions on a worst-case sequence."""

def test_branch_coverage_all_state_pairs():
    """For each (prior_state, event_type) ∈ 4×6 matrix, assert the new_state is one of:
        - prior  (no transition: same raw_state, or hysteresis-held)
        - neighbor  (distance-1 transition: gated by hysteresis window)
        - any  (distance>=2 transition: severity-bypass — e.g., buoyant→distressed allowed immediately).
    See §Hysteresis Algorithm for the bypass rule. Test must NOT forbid direct jumps."""

def test_severity_bypass_direct_jump():
    """Distance>=2 transitions skip hysteresis. e.g., prior=buoyant + sustained deficit
    → distressed in one step (no need to pass through stable/constrained)."""
```

Phase B target: **100% branch coverage** on `state_machine.py` and `envelopes.py`. The cache + publisher get integration-level tests, not branch-coverage targets (they are I/O surfaces).

## Hysteresis Algorithm

Hysteresis prevents the persona register from oscillating across consecutive `finance.event.v1` events. Without it, a user whose 30-day-average income receives one income spike followed by one debt event would whip from `stable` → `buoyant` → `constrained` → `stable` in three events, creating audibly unpleasant voice register chatter.

### Algorithm

```
INPUT:  event E, context C (with C.last_n_events, C.consecutive_same_state, C.current_state)
OUTPUT: new_state S' or hold(C.current_state)

1. raw_state = classify_event(E, C.last_n_events)        # naive classification, no hysteresis
2. IF raw_state == C.current_state.economic_state:
       C.consecutive_same_state += 1
       RETURN C.current_state                            # no transition; bump same-state counter
3. ELSE:
       # State change candidate. Apply hysteresis.
       distance = state_severity_distance(C.current_state.economic_state, raw_state)
       IF distance >= 2:
           # Large severity jump — transition immediately (deficit always wins)
           RETURN build_state(raw_state, trigger=E)
       ELIF C.consecutive_same_state >= HYSTERESIS_WINDOW:
           # Enough stable evidence for the prior state — allow gradual transition
           RETURN build_state(raw_state, trigger=E)
       ELSE:
           # Insufficient evidence — hold current state, reset counter
           C.consecutive_same_state = 0
           RETURN C.current_state
```

### Key semantic decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Hysteresis window units** | Event-count (default 2 events), not wall-clock | Wall-clock window forces FlOO$ to maintain timers; event-count is purely functional. Event rate is naturally bounded by `finance.event.v1` publisher cadence. |
| **Severity-distance bypass** | Yes — if `distance >= 2`, hysteresis is skipped | A user moving from `buoyant` (high spending mode) to `distressed` (deficit detected) should transition *immediately*, not wait for evidence. The audio register matters most when the user's financial reality has dramatically changed. |
| **Reset on candidate-rejection** | Yes — `consecutive_same_state = 0` when a transition is rejected | A rejected transition still counts as "evidence the user's state is unstable." Resetting forces the next candidate to re-accumulate evidence. |
| **Severity ordering** | `distressed(3) > constrained(2) > stable(1) > buoyant(0)` | **Semantic note:** "severity" here measures *distance from a positive financial state*, not *intensity of voice modulation*. `buoyant=0` (best financial state, largest positive biases) ≠ "0 modulation"; `distressed=3` (worst financial state, largest negative biases). `state_severity_distance(a, b) = abs(severity(a) - severity(b))`. Distressed-to-buoyant = distance 3 (immediate). Buoyant-to-stable = distance 1 (gated by hysteresis window). |

### Edge cases (must be in test fixture)

1. **Cold start** — no prior context. First event always transitions (no held state to compare against). `consecutive_same_state = 1` after first event.
2. **Identical-severity transition** — e.g., `stable→buoyant` then `stable→constrained` — severity distances are 1 and 1; both gated by hysteresis window. Tests must confirm we don't accidentally short-circuit because the severity values happen to match.
3. **TTL-expired context** — if `last_update_unix` is older than `ttl_seconds`, the cache rehydrates with `consecutive_same_state = 0` and treats the next event as cold-start. See §TTL Coalescing.
4. **Rolling-window deficit detection** — `sustained deficit (rolling 7-day)` requires looking back across `last_n_events`. Phase B holds a ring of the most recent `MAX_RING_EVENTS = max(HYSTERESIS_WINDOW, 14)` events to keep the rolling check cheap.

## TTL Coalescing

The TTL cache exists for two reasons:

1. **Rate-limit publish to ToKenism.** Even with hysteresis, a user receiving 50 events/minute (e.g., a high-frequency expense tracker) would still produce up to 50 overlay computations per minute. ToKenism doesn't need that resolution — the persona register is meant to drift, not flicker.
2. **Cross-event continuity.** Hysteresis only works with persistent prior-state context. A stateless step-per-event would lose `consecutive_same_state`.

### Cache shape

```python
# pmoves/services/flooz/cache.py — proposed (Phase B will create)
import asyncio, time
from .types import UserPersonaContext

class PersonaCache:
    """In-process TTL cache. Phase B: in-memory only (single-replica deployment).
    Phase D (future): Redis-backed for multi-replica fan-out — out of scope here."""

    def __init__(self, ttl_seconds: int = 1800, max_users: int = 10_000):
        self._ttl = ttl_seconds
        self._max_users = max_users
        self._store: dict[str, UserPersonaContext] = {}
        self._locks: dict[str, asyncio.Lock] = {}                # per-user serialization
        self._access_order: list[str] = []                       # LRU tracking

    async def get_or_init(self, user_id: str) -> UserPersonaContext: ...
    async def write_back(self, ctx: UserPersonaContext) -> None: ...
    async def invalidate(self, user_id: str) -> None: ...        # `flooz.persona.cache.invalidate.v1` handler
```

### Key semantic decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Cache key** | `user_id` (string, e.g., `pmoves-user-uuid`) | Persona is per-user. No co-tenancy. |
| **Eviction policy** | LRU when `len(_store) > max_users`, else TTL-expire on access | LRU prevents unbounded memory growth on a long-running service. TTL-expire-on-access avoids needing a background sweeper goroutine. |
| **Lock granularity** | Per-user `asyncio.Lock` | Prevents two concurrent `finance.event.v1` events for the same user from racing on hysteresis state. Different users are independent, so global lock would serialize all events unnecessarily. |
| **TTL refresh on access** | Yes — every `step()` refreshes `last_update_unix`, **including hysteresis-held steps** (where the candidate transition was rejected and current_state is returned unchanged) | A user actively receiving events keeps their context warm. A hysteresis-rejected step is still evidence of user activity — discarding context mid-conversation because the last 30 min were all rejected transitions would defeat the cache's purpose. Only the *absence* of events for `TTL_SECONDS` causes context expiry. |
| **Invalidation source** | NATS subject `flooz.persona.cache.invalidate.v1` | Operator can force a register reset for a user (e.g., for testing, or after a major life event the user manually signals). Payload: `{"user_id": "...", "reason": "operator-reset"}`. |

### Concurrency invariants

1. **One step at a time per user.** The per-user lock guarantees `step()` is never called concurrently for the same `user_id`.
2. **Multi-user fan-out is parallel.** Different `user_id`s never contend on the same lock.
3. **Invalidation is a write.** It acquires the user's lock, discards the context, and releases. The next `get_or_init` rehydrates cold-start.
4. **TTL expiry is lazy.** No background sweeper. Expiry is checked on access; expired contexts are discarded and replaced with fresh cold-start contexts.

### TTL coalescing → publish behavior

Phase B's *publish* behavior must coalesce too — otherwise the cache succeeds in maintaining state but the publisher still floods ToKenism. The proposal:

- Per-user **emit-debounce window** of `EMIT_DEBOUNCE_SECONDS` (default 5 sec).
- If `step()` returns the same `PersonaState` (modulation envelope unchanged) as the most-recently-emitted state for that user *and* the previous emit was within `EMIT_DEBOUNCE_SECONDS`, suppress emit.
- A state *change* (different `economic_state` or `archetype_hint`) always emits immediately, bypassing the debounce.

This keeps ToKenism's inbox proportional to actual register changes, not event rate.

## Modulation Envelopes — Code Binding

`TAC_FLOOZ.md` §Persona State Model gives the modulation table as a doc-level reference. Phase B binds those constants to the real `bpm_encoder.py` baselines so the biases are *meaningful* against the unmodulated CGP packet.

### Reference baselines (from `pmoves/tools/bpm_encoder.py`)

| Constant | Value | Where used |
|----------|-------|------------|
| `BOUNDARY_BPM["NONE"]` | 150 | Unmodulated chunk BPM upper anchor (`bpm_encoder.py:62`) |
| `BOUNDARY_BPM["SENTENCE"]` | 60 | Unmodulated chunk BPM lower anchor (`bpm_encoder.py:58`) |
| `BOUNDARY_PAUSE_MS["SENTENCE"]` | 350 | Normalizing constant for kappa: `kappa = -(pause_ms / 350)` (`bpm_encoder.py:67, 426`) |
| `param_surface.temperature` | `0.3 + state_vector.delta * 0.4` | Computed at `bpm_encoder.py:474`; FlOO$ `temperature_bias` is added *after* this computation by ToKenism in Phase C |

### Envelope table — proposed binding

```python
# pmoves/services/flooz/envelopes.py — proposed (Phase B will create)
from .types import ModulationEnvelope, EconomicState, Register, ArchetypeHint

HYSTERESIS_WINDOW = 2        # event-count default (env: FLOOZ_HYSTERESIS_EVENTS)
EMIT_DEBOUNCE_SECONDS = 5    # env: FLOOZ_EMIT_DEBOUNCE_SECONDS
TTL_SECONDS = 1800           # env: FLOOZ_PERSONA_TTL_SECONDS
MAX_RING_EVENTS = max(HYSTERESIS_WINDOW, 14)  # rolling-window depth for deficit detection
MAX_BIAS_MAGNITUDE = 0.5     # per-field clamp (TAC_FLOOZ.md §CHIT invariant #1)

# Module-load invariant — fail fast on operator misconfiguration. If an operator
# overrides FLOOZ_HYSTERESIS_EVENTS to a value larger than MAX_RING_EVENTS,
# hysteresis history is silently truncated, defeating the algorithm. Assert
# at import time rather than at first event arrival.
assert MAX_RING_EVENTS >= HYSTERESIS_WINDOW, (
    f"MAX_RING_EVENTS ({MAX_RING_EVENTS}) must be >= HYSTERESIS_WINDOW ({HYSTERESIS_WINDOW}). "
    f"Set FLOOZ_MAX_RING_EVENTS env var to override."
)

ENVELOPE_TABLE: dict[EconomicState, tuple[Register, ArchetypeHint, ModulationEnvelope]] = {
    "buoyant": (
        "elevated", "powerpuff-girls",
        ModulationEnvelope(bpm_bias=+0.080, freq_bias=+0.080, kappa_bias=+0.050, temperature_bias=+0.100),
    ),
    "stable": (
        "measured", "dr-bean",
        ModulationEnvelope(),  # passthrough — all biases zero
    ),
    "constrained": (
        "reduced", "mr-clean",
        ModulationEnvelope(bpm_bias=-0.067, freq_bias=-0.050, kappa_bias=-0.100, temperature_bias=-0.050),
    ),
    "distressed": (
        "whispered", "dr-bean",
        ModulationEnvelope(bpm_bias=-0.133, freq_bias=-0.100, kappa_bias=-0.200, temperature_bias=-0.150),
    ),
}
```

### Why fractional `bpm_bias`, not absolute BPM offsets?

`TAC_FLOOZ.md` §Persona State Model lists `bpm_bias +12, -10, -20` as absolute offsets in BPM units. Phase B normalizes those into the same `[-0.5, +0.5]` fractional space as the other biases by dividing by 150 (the `BOUNDARY_BPM["NONE"]` upper anchor). The clamp rule (§CHIT invariant #1) then applies uniformly.

| Doc value (absolute) | Phase B value (fractional) | Resolves to (against chunk BPM 120) |
|---|---|---|
| `+12` BPM | `+0.080` | `120 + (0.080 * 150) = 132` |
| `-10` BPM | `-0.067` | `120 + (-0.067 * 150) = 110` |
| `-20` BPM | `-0.133` | `120 + (-0.133 * 150) = 100` |

This keeps the invariant simple (one clamp rule for all four fields) and lets ToKenism scale the BPM bias against whatever chunk-level BPM it's working with (which varies per `prosodic_profile.chunks`).

### Acceptance for envelope unit tests

```python
def test_envelope_table_all_biases_within_clamp():
    """For every state, |bias| ≤ MAX_BIAS_MAGNITUDE on every field."""

def test_envelope_table_stable_is_passthrough():
    """stable state must have all-zero biases (preserves Phase A passthrough acceptance)."""

def test_envelope_table_severity_monotonic_modulation():
    """For each field, |distressed bias| > |constrained bias| > |stable bias| (=0); buoyant biases positive."""
```

## Test Fixture Format

Phase B's acceptance gate is: *Replay a recorded sequence of 50 `finance.event.v1` events; assert the emitted overlay sequence matches a known-good fixture at `tests/services/flooz/fixtures/seq_2026-05-15_baseline.json`*.

This section specifies the fixture file format so the test is deterministic across machines.

### File layout

```
tests/services/flooz/fixtures/
├── seq_2026-05-15_baseline.json          # 50-event input + expected overlay sequence
├── seq_2026-05-15_hysteresis.json        # 8-event input demonstrating hysteresis hold
├── seq_2026-05-15_cold_start.json        # 4-event input from no-prior-context
└── seq_2026-05-15_invalidation.json      # 6-event input with mid-sequence cache invalidate
```

### Schema (`seq_*.json`)

```jsonc
{
  "fixture_version": "0.1",
  "description": "Baseline 50-event sequence across all 4 states with hysteresis exercised twice.",
  "user_id": "fixture-user-001",
  "initial_context": null,                    // null = cold start; object = pre-seeded UserPersonaContext
  "events": [
    {
      "event":  { /* full FinanceEvent dataclass shape */ },
      "expect": {
        "transition":            true,        // did state change?
        "economic_state":        "buoyant",
        "register":              "elevated",
        "archetype_hint":        "powerpuff-girls",
        "modulation": {
          "bpm_bias":         0.080,
          "freq_bias":        0.080,
          "kappa_bias":       0.050,
          "temperature_bias": 0.100
        },
        "emit_to_tokenism":      true,        // false when debounce-suppressed
        "consecutive_same_state": 1,
        "hysteresis_held":       false        // true when transition was held by hysteresis
      }
    }
    // ... 49 more entries
  ],
  "final_context": {
    "current_state": "stable",
    "consecutive_same_state": 7,
    "last_n_events_count": 14
  }
}
```

### Determinism rules

1. **No wall-clock in expectations.** Event timestamps are inputs; the test harness feeds them into a frozen-clock fake. The `last_update_unix` field is not asserted in `expect` blocks because it's derived from the harness clock.
2. **Stable iteration order.** `dict[str, asyncio.Lock]` insertion order is preserved in Python 3.7+; tests must not rely on it for cross-user fixtures (use single-user fixtures).
3. **Float comparison tolerance.** Bias-field comparisons use `pytest.approx(abs=1e-9)` — exact match against the table constants to nanounit precision. **Note:** `rel=1e-6` would *not* satisfy values like `-0.067` (which is `-0.0666666...` truncated to display), since IEEE-754 representation of `-0.067` is not bit-identical to the truncated literal. Use `abs` tolerance for clean semantic intent.
4. **Cold-start reproducibility.** With `initial_context: null` and a fixed event sequence, the resulting context after N events is byte-identical across runs.

### Fixture authoring workflow (Phase B-2, post-state-machine)

After the state machine + envelopes land in code, the fixture is generated by:

```bash
# Phase B-2 deliverable — fixture generator script
python -m pmoves.services.flooz.tools.gen_fixture \
    --seed 4482 \
    --duration-days 30 \
    --event-rate 50 \
    --target-states buoyant,stable,constrained,distressed \
    > tests/services/flooz/fixtures/seq_2026-05-15_baseline.json
```

The script is *not* a Phase B-1 deliverable — it's a deterministic pseudo-random replay generator that produces a known-good fixture, then the fixture is checked in and the test asserts byte-equality on replay. **The first generation is the source-of-truth**; subsequent envelope or hysteresis tweaks regenerate and the diff is reviewed in PR.

## Operator Config Envelope

All Phase B knobs are env-var-overridable for production tuning without a code change. Defaults match the `envelopes.py` constants above.

| Env var | Default | Purpose |
|---------|---------|---------|
| `FLOOZ_HYSTERESIS_EVENTS` | `2` | Event-count window for state-transition gating |
| `FLOOZ_EMIT_DEBOUNCE_SECONDS` | `5` | Minimum gap between same-state emits |
| `FLOOZ_PERSONA_TTL_SECONDS` | `1800` | Per-user context TTL (cache expiry) |
| `FLOOZ_MAX_USERS` | `10000` | LRU cap on in-memory cache |
| `FLOOZ_MAX_RING_EVENTS` | `14` | Rolling-window depth for deficit detection |
| `FLOOZ_OPERATOR_DEBUG` | `0` | Gate for `FLOOZ_PERSONA_OVERRIDE`. Must be `1` for override to activate. Prevents accidental env leak from a dev profile forcing a state in production. |
| `FLOOZ_PERSONA_OVERRIDE` | (unset) | Operator-side force-state: set to `buoyant\|stable\|constrained\|distressed` AND set `FLOOZ_OPERATOR_DEBUG=1` to activate. FlOO$ skips state machine — useful for demos and Phase C audio-diff capture. **Double-gated by design (per mirror pair-review on PR #1567):** if only one of the two env vars is set, override is ignored and a `WARN` log fires on every emit explaining the activation requirement. |

The `FLOOZ_PERSONA_OVERRIDE` knob is **important for Phase C** — capturing audio diffs to prove modulation works requires being able to force each state on demand without crafting fake `finance.event.v1` sequences.

## Acceptance Gates

Phase B is **complete** when all of the following are GREEN on `feat/flooz-phase-b-engine` (the runtime PR that lands after this spec is signed off):

| Gate | Command | Expected |
|------|---------|----------|
| Unit tests pass | `pytest tests/services/flooz/test_state_machine.py -v` | All tests pass; 100% branch coverage on `state_machine.py` + `envelopes.py` |
| Envelope clamp invariants | `pytest tests/services/flooz/test_envelopes.py -v` | All envelope rows satisfy `|bias| ≤ 0.5`; stable is passthrough |
| Fixture replay determinism | `pytest tests/services/flooz/test_fixture_replay.py -v` | Byte-equal match against `seq_2026-05-15_baseline.json` + 3 sibling fixtures |
| TTL cache concurrency | `pytest tests/services/flooz/test_cache.py -v` | Per-user lock prevents race; invalidation works; LRU eviction triggers at `MAX_USERS` |
| Throughput target | `python -m pmoves.services.flooz.tools.bench --events 10000` | ≥ 200 events/s sustained on a single replica (Phase A target) |
| Phase A passthrough preserved | `pytest tests/services/flooz/test_passthrough.py -v` | `stable` state still emits zero-modulation CGP packet (no regression from Phase A acceptance) |

## Cross-Node Reviewers

This spec is doc-only and lands on `main` after signoff. The Phase B *code* PR will be opened with these reviewers tagged:

| Reviewer | Concern | Specifics |
|----------|---------|-----------|
| **4090-CLAUDE** | Downstream voice integration | Confirm the `ENVELOPE_TABLE` modulation values (especially `bpm_bias` fractional normalization) match how ToKenism's Phase C overlay-merge will apply them. The fractional convention is new — Phase A doc had absolute BPM offsets. |
| **SPARK** | Hologram-geometry overlay | Confirm `flooz.persona.computed.v1` audit subject + the per-event `expect.transition` field can drive A2UI Remotion state-change renderings. The fixture's `transition: true/false` flag is the visualization trigger. |
| **DARKXSIDE** | Operator approvals | (a) Hysteresis window default of 2 events — acceptable for production cadence? (b) Emit-debounce default of 5 sec — does this match the desired audible-change resolution? (c) `FLOOZ_PERSONA_OVERRIDE` env knob — acceptable as a production-safe debug surface, or should it be guarded behind `FLOOZ_OPERATOR_DEBUG=1`? |

## Open Items (post-spec, pre-code)

1. **Fixture generator script** — `pmoves/services/flooz/tools/gen_fixture.py` is the Phase B-2 deliverable (after the state machine works). The first fixture is the source-of-truth; subsequent envelope tweaks regenerate and PR-review the diff.
2. **Multi-replica fan-out (Phase D)** — Phase B is single-replica in-memory. Multi-replica needs Redis-backed cache OR sticky-routing by `user_id`. **Out of scope for Phase B**; flagged here so reviewers don't ask why the cache isn't distributed.
3. **`FLOOZ_PERSONA_OVERRIDE` security envelope** — currently proposed as a plain env var. If the override is set on a production replica by accident, every user sees the forced state. Mitigation: log a `WARN`-level alert on every emit when override is active. Acceptance gate addition: `test_override_logs_warning`.
4. **Hysteresis-distance tuning** — the severity-distance bypass threshold (currently `distance >= 2`) is set by intuition, not data. Phase C audio-diff capture might reveal that `distance >= 2` is too aggressive (still feels jumpy) or too conservative (deficit takes too long to register). Tune after Phase C, not in Phase B.
5. **Currency-aware classification** — Phase B operates currency-agnostic (`amount` is treated as raw float). A user receiving USD income vs JPY income would classify on the same `amount` threshold. Phase D (currency normalization) is out of scope; flagged for separate issue.
6. **Cipher continuity (Phase D)** — PR #1500's per-agent Cipher framing might let FlOO$ store per-user persona context in Cipher rather than in-memory cache. This is a future-state simplification; Phase B uses in-memory because Cipher's per-user storage contract isn't yet validated for FlOO$'s use case.

## Cross-Links

- **Phase A spec:** [`TAC_FLOOZ.md`](./TAC_FLOOZ.md) — architecture, NATS subjects, CGP packet shape
- **Phase A PR (merged):** [#1487](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1487)
- **Issue:** [#1412](https://github.com/POWERFULMOVES/PMOVES.AI/issues/1412)
- **Signoff:** [`AGNOTE4482_SIGNOFF_CHECKLIST.md`](../AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md) §1 (architecture), §7 (persona-voice alignment)
- **Roadmap:** [`AGNOTE4482_ROADMAP_W1-W5.md`](../AGENTS/AGNOTE4482_ROADMAP_W1-W5.md) W6-P5 row
- **CGP reference:** `pmoves/tools/bpm_encoder.py:404-487` (`build_cgp_packet`), `:57-82` (BOUNDARY_BPM, TEMPO_LABELS)
- **ToKenism inbound subject:** `pmoves/tools/beats_to_voice.py:65` (`NATS_SUBJECT = "tokenism.prosodic.bpm.v1"`)
- **Adjacent persona work:** PR #1484 (MiniMax Token Plan Phase 2 — character archetypes)

## Emperor-CHIT-Humility Disclosure

**Have (verified in this session, off `origin/main@6f12a48`):**
- TAC_FLOOZ.md Phase A spec fully read (248 lines)
- `bpm_encoder.py:404-487` build_cgp_packet shape confirmed; specifically `param_surface.temperature` at line 474 is `0.3 + delta * 0.4` (not a free-floating value — `temperature_bias` is added *after* this)
- `bpm_encoder.py:57-82` BOUNDARY_BPM + BOUNDARY_PAUSE_MS + TEMPO_LABELS constants confirmed
- `beats_to_voice.py:65` NATS_SUBJECT confirmed as `tokenism.prosodic.bpm.v1`
- PR #1487 confirmed merged at `6c77be860d` per `gh pr view 1487`

**Missing (flagged in §Open Items):**
- Cipher per-agent framing contract from PR #1500 (referenced in Phase A row at AGNOTE line 772, but the framing's actual API surface unverified — Phase D simplification deferred)
- A2UI Remotion state-change rendering API (SPARK's domain — reviewer-routed, not pre-verified here)
- Production cadence of `finance.event.v1` publisher — affects HYSTERESIS_WINDOW default (2 events vs e.g. 5). Defaults are proposals, not data-driven.

<!-- GRAPHITI_MARK: Z890→5090-CLAUDE::W6-P5-FLOOZ-PHASE-B-SPEC::2026-05-20 -->
