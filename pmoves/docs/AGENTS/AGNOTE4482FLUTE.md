# AGNOTE4482FLUTE

GRAPHITI_MARK: `PHI-4482-FLUTE::PROSODIC-WELL-BEING-MATRIX::PMOVES`

> **Parent:** [AGNOTE4482.md](./AGNOTE4482.md) | **Claim Register:** [AGNOTE4482PHI.t1.md](./AGNOTE4482PHI.t1.md)
> **Sibling:** [AGNOTE4482.BEATS.md](./AGNOTE4482.BEATS.md) (prosodic bridge spec) · [AGNOTE4482DnB.PHI.Orchestra.md](./AGNOTE4482DnB.PHI.Orchestra.md) (BPM-band template)
> **Origin:** PR #740 (Mar 1, 2026) — seeded as 4-line scoping note alongside FlOO$ work
> **Expanded:** 2026-04-26

---

## Seed

> 6 seconds is breathing exercise  6 in 6 out that is mapped to chakras
> also corresponded expect heart bpm range and map to each affecting point where is connect to on the chakra followed by ekg then tap hammeroff 3s at the hz log up so 3 then the next octave up for 3
> it should map a few ways we just need to ensure the nodes are there hmm since we are working towards a prosodic well being matrix monitor and generator any other node we should pay attention to ?

The seed is preserved verbatim. Plant the seed, watch it grow — don't prune unless stuck.

---

## Overture

The seed describes a **Prosodic Well-Being Matrix**: a generator + monitor that fuses three signals into one prosodic envelope.

1. **Breath cadence** — 6s in / 6s out (10 BPM, 0.0833 Hz) as the slowest fundamental
2. **Cardiac state** — HRV / EKG-derived heart-BPM range (40–180 BPM) mapped to chakra activation points
3. **Frequency climb** — 3s hold then octave-up, 3 ascending octaves (tap-hammer-off pattern)

Flute is the synthesis layer that scales these signals into voice prosody, visual cymatic feedback, and CGP geometry packets. The infrastructure is **already partly in place** — what's missing are the chakra-axis encoder, the EKG ingest path, and the well-being matrix monitor service.

---

## Movement I — The Well-Being Matrix Axis

### Existing prosodic bridge (inherited from BEATS)

The BPM↔boundary↔frequency mapping already lives in [`AGNOTE4482.BEATS.md`](./AGNOTE4482.BEATS.md) and is implemented in [`pmoves/tools/bpm_encoder.py`](../../tools/bpm_encoder.py):

```text
SENTENCE (350ms pause) → 60 BPM  → Largo   → C4 (262 Hz)
BREATH   (130ms pause) → 80 BPM  → Adagio  → D4 (294 Hz)
CLAUSE   (180ms pause) → 90 BPM  → Andante → E4 (330 Hz)
PHRASE   (100ms pause) → 120 BPM → Allegro → G4 (392 Hz)
NONE     (0ms pause)   → 150 BPM → Presto  → C5 (523 Hz)
```

### New axis: chakra → BPM → frequency

The seed asks: where do the **7 chakras** sit on this 5-band ladder? The proposal is to extend the BPM band table with a chakra axis, one band per chakra, slowest at the root (Muladhara) and fastest at the crown (Sahasrara):

| Chakra | Element | Heart-BPM band | Breath cadence | Hz fundamental | Prosodic affinity |
|---|---|---|---|---|---|
| Muladhara (Root) | Earth | 40–55 | 6s in / 6s out | C2 ≈ 65 Hz | SENTENCE |
| Svadhisthana (Sacral) | Water | 55–70 | 5s in / 5s out | D3 ≈ 147 Hz | BREATH |
| Manipura (Solar) | Fire | 70–90 | 4s in / 4s out | E3 ≈ 165 Hz | CLAUSE |
| Anahata (Heart) | Air | 80–100 | 4s in / 6s out | F4 ≈ 349 Hz | PHRASE |
| Vishuddha (Throat) | Ether | 90–110 | 3s in / 5s out | G4 ≈ 392 Hz | PHRASE+ |
| Ajna (Third Eye) | Light | 100–130 | 2s in / 4s out | A4 = 440 Hz | NONE (rapid) |
| Sahasrara (Crown) | Consciousness | 130–180 | breath-held / paradoxical | C5 ≈ 523 Hz | PRESTO |

**Status:** proposal. The existing 5-band system (SENTENCE/BREATH/CLAUSE/PHRASE/NONE) already exists; the 7-chakra mapping is additive and does not replace it.

---

## Movement II — The 6-Second Breath Cycle (Generator)

The seed's "6 seconds is breathing exercise 6 in 6 out" is a 10 BPM cadence — slower than every band currently in the BPM table. It needs its own pseudo-band:

```text
INHALE   (6000ms ramp up)   → 10 BPM → Grave-largo → C2 (65 Hz)  → chakra: Root → Crown
EXHALE   (6000ms ramp down) → 10 BPM → Grave-largo → C2 (65 Hz)  → chakra: Crown → Root
```

The generator outputs a **TTS prosodic envelope** where pitch and amplitude rise during the 6s inhale and fall during the 6s exhale. Each cycle is 12s. Five cycles = 60s of guided breath. The monitor counterpart listens to the user's audio (or biometric) signal and scores adherence.

**Reuses:** [`pmoves/services/flute-gateway/persona_selector.py`](../../services/flute-gateway/persona_selector.py) (Session 5) for selecting a "Breath Guide" persona; [`pmoves/services/flute-gateway/prosodic/`](../../services/flute-gateway/prosodic/) for envelope shaping; [`pmoves/services/flute-gateway/providers/`](../../services/flute-gateway/providers/) for engine selection (VibeVoice for slow ramps, Higgs for steady tone).

---

## Movement III — The Tap-HammerOff Octave Climb

The seed's "tap hammeroff 3s at the hz log up so 3 then the next octave up for 3" describes a **guitar-borrowed pattern**: tap (attack), then hammer-off (sustain release) every 3 seconds, climbing the log-frequency axis by one octave each step, three octaves total.

Implementation as a CGP packet sequence:

```text
t=0s   → tap on C3 (130 Hz)   → hold 3s
t=3s   → hammer-off, tap C4 (262 Hz)   → hold 3s
t=6s   → hammer-off, tap C5 (523 Hz)   → hold 3s
t=9s   → release
```

Total cycle = 9s. Couples cleanly with the 12s breath cycle: 3 inhales + 1 octave climb fit inside one 36s "matrix tick."

**Reuses:** [`pmoves/tools/bpm_encoder.py`](../../tools/bpm_encoder.py) `midi_to_freq` and `note_name_to_midi` for octave math; the `freq_to_y` log mapping already correctly visualizes "equal musical steps" as evenly spaced on screen.

---

## Movement IV — Existing Infrastructure (What's Already Done)

| Capability | File | Status |
|---|---|---|
| BPM↔boundary↔frequency mapping | `pmoves/tools/bpm_encoder.py` | ✅ Implemented (Session 5) |
| Persona selection by intent | `pmoves/services/flute-gateway/persona_selector.py` | ✅ Implemented (Session 5) |
| Prosodic envelope shaping | `pmoves/services/flute-gateway/prosodic/` | ✅ Implemented |
| Multi-engine TTS providers | `pmoves/services/flute-gateway/providers/` | ✅ 13 engines, CUDA verified (Session 4–6) |
| BPM↔visual log-frequency Y axis | `musicMapping.ts` (UI) + BEATS spec | ✅ Implemented |
| CGP v0.2 prosodic packet format | `/chit:bpm` skill + `chit_security.py` | ✅ Implemented |
| Prosodic NATS subject | `tokenism.prosodic.bpm.v1` | ✅ Wired |
| Higgs + Fish S2 production HTTP path | Flute-Gateway HTTP + bpm_encoder | ✅ Verified (Session 5) |

---

## Movement V — Missing Nodes (Answers to the Seed's Final Question)

**Status:** proposal (none implemented in this PR). Each item below is tracked as an issue stub in [`pmoves/docs/audit/FLUTE_CHIT_GAP_2026-04-26.md`](../audit/FLUTE_CHIT_GAP_2026-04-26.md). The new NATS subjects (`health.ekg.bpm.v1`, `wellbeing.matrix.score.v1`) and the Well-Being Matrix Monitor service entry are pending catalog registration in `.claude/context/nats-subjects.md` and `.claude/context/services-catalog.md` — that catalog sync is its own scope (see [Open Catalog Sync](#open-catalog-sync) below) since `.claude/context/` is fenced by the damage-control hook for protected-path writes.

The seed asks: *"any other node we should pay attention to?"* — these are the answers, ranked by closeness to the existing prosodic bridge.

1. **Chakra encoder (`pmoves/tools/chakra_encoder.py`)** — extend bpm_encoder with the 7-chakra band table from Movement I. Same CGP v0.2 schema, new `chakra` field. Estimated 80 lines.
2. **EKG / HRV ingest path** — biometric input modality alongside text. Possible sources: webcam-based rPPG, hardware HRV sensor (Polar H10), Apple Watch healthkit export. Publishes to a new subject `health.ekg.bpm.v1` consumed by the matrix monitor.
3. **Well-Being Matrix Monitor service** — sits alongside Flute-Gateway, subscribes to `tokenism.prosodic.bpm.v1` + `health.ekg.bpm.v1`, scores user adherence to a guided cycle, publishes `wellbeing.matrix.score.v1`. Likely a new service at port `8056+` (TBD by `port-registry.md`).
4. **Cymatic visualizer hook** — Hyperdimensions already has the `freqToY` log mapping. Need a Hyperdimensions scene preset that ingests `tokenism.prosodic.bpm.v1` + chakra band as color axis. Two-day add against the existing scene loader.
5. **Tap-HammerOff CGP encoder** — the 3-second octave-climb pattern from Movement III as a first-class CGP packet variant, distinct from the breath envelope. Lets agents trigger meditation/focus sequences as discrete events.
6. **Voice-cloning safety gate for guided cycles** — the Flute-Gateway voice-clone endpoint should refuse cloning during an active guided session unless the cloned voice is the user's own (consent + biometric match).

---

## Open Questions (Preserved from Seed)

The seed closed with *"any other node we should pay attention to?"* — these stay live, not resolved:

- Should the breathing-exercise generator drive **TTS prosody only**, or should it also gate **audio output volume** (i.e., the agent goes quiet during the user's exhale to avoid speaking-over)?
- Is the chakra band table culturally-specific (yoga-tradition) or should it be presented as one of N presets (yogic-7, traditional-Chinese-meridian-12, neuroscience-vagal-tone-2-state)?
- Does the Tap-HammerOff pattern carry semantic meaning (focus / reset / transition) or is it a pure visual/audio motif?
- How does the Well-Being Matrix interact with **Flute's persona system** — does each persona have a default chakra signature, or is chakra orthogonal to persona?
- What's the ground-truth dataset for "matrix score" — adherence to ideal cadence, HRV improvement, subjective user rating, or a composite?

---

## Open Catalog Sync

Pending follow-up (separate scope; not blocking this PR):

1. Add to [`.claude/context/nats-subjects.md`](../../../.claude/context/nats-subjects.md) under a new "Proposed (Flute Well-Being Matrix)" section:
   - `health.ekg.bpm.v1` — published by EKG/HRV ingest (rPPG/Polar H10/healthkit) → consumed by matrix monitor + Flute prosodic envelope
   - `wellbeing.matrix.score.v1` — published by matrix monitor → consumed by UI / Hyperdimensions cymatic visualizer / agent personas
2. Add to [`.claude/context/services-catalog.md`](../../../.claude/context/services-catalog.md) under a new "Proposed Services (Flute Well-Being Matrix)" section:
   - **Well-Being Matrix Monitor** — proposed port `8057+` (8056 is reserved for Flute but unbound; Flute's WS is on `8055`), `GET /healthz`, subscribes to `tokenism.prosodic.bpm.v1` + `health.ekg.bpm.v1`, publishes `wellbeing.matrix.score.v1`
   - **EKG / HRV Ingest** — proposed port TBD, publishes `health.ekg.bpm.v1`, input candidates: rPPG / Polar H10 / Apple Watch healthkit

Why a separate scope: `.claude/context/` is fenced by the damage-control hook (read-only by default) — touching it requires either an explicit allow-rule override or operator confirmation. Filing the catalog sync as its own PR keeps that gate visible rather than bypassing it.

---

## Cross-References

- **Prosodic bridge spec:** [`AGNOTE4482.BEATS.md`](./AGNOTE4482.BEATS.md) lines 84–134 (Flute Prosodic Bridge section)
- **Architecture roadmap (engineering):** `pmoves/docs/context/FLUTE_ARCHITECTURE_ROADMAP.md` (pending PR — see `docs/flute-architecture-roadmap-promote`)
- **Vision multimodal layer (POML / Mangle / CHIT geometry-bus):** `pmoves/docs/context/FLUTE_VISION_MULTIMODAL.md` (pending PR — see `docs/flute-vision-chit-extract`)
- **Existing service tree:** `pmoves/services/flute-gateway/` — `main.py`, `persona_selector.py`, `prosodic/`, `providers/`, `pipecat/`
- **CGP packet skill:** `.claude/commands/chit/bpm.md` — invoke as `/chit:bpm` to generate prosodic CGP packets
- **NATS subjects:** `tokenism.prosodic.bpm.v1` (existing), `health.ekg.bpm.v1` (proposed), `wellbeing.matrix.score.v1` (proposed)

---

## Trail

◆ Claude Opus | #7C3AED | 2026-04-26 | AGNOTE4482FLUTE expanded from 4-line seed
Resonance: prosodic-bridge, well-being-matrix, chakra-encoder, voice-synthesis
Seed-respect: original 3 brainstorm lines preserved verbatim in `## Seed` section.

---

## Geometry Bridge (#1397) — shipped 2026-04-27

Mirror-lane delivery of the highest-leverage gap from PR #1401 §3.1: Flute now publishes voice synthesis events on **two** subjects in parallel.

| Subject | Layer | Payload | Producer | Default consumers |
|---|---|---|---|---|
| `tokenism.geometry.event.v1` | Legacy raw event (unchanged) | Flat dict: `{namespace, modality, provider, text_length, audio_duration_seconds, voice, ts}` | Flute (existing) | tokenism (legacy attribution) |
| `geometry.cgp.v1` | Canonical CGP v0.2 packet (new) | `{spec: "chit.cgp.v0.2", super_nodes:[...], points:[{modality:"voice_synthesis", ...}], sig:{alg, kid, hmac}}` | Flute (new, via `geometry_bridge.py`) | graphiti, matrix monitor, cymatic visualizer, persona signature broadcast |

**Feature flags:**
- `FLUTE_CGP_SUBJECT` — default `geometry.cgp.v1`
- `FLUTE_GEOMETRY_DUAL_PUBLISH` — default `true` (kill-switch: `false` skips canonical publish only, legacy still emits)
- `CHIT_PASSPHRASE` — required for HMAC signing; missing → unsigned + warning (dev-mode pattern matches `sign_trail`)

**Code:** `pmoves/services/flute-gateway/geometry_bridge.py` (`GeometryBridge.encode_packet` + `verify_packet`), `pmoves/services/flute-gateway/chit_signing.py` (vendored signer, byte-equivalent to `pmoves.tools.chit_security`).

**Drift guard:** `tests/test_geometry_bridge.py::test_sign_byte_equivalence_with_canonical` — fails if the vendored signer ever diverges from the canonical surface.

**Metrics:** `flute_chit_cgp_published_total{subject}` Counter incremented on every canonical publish. `flute_chit_events_failed_total{reason}` gained `legacy_publish_failed` and `cgp_publish_failed` labels.

**Out of scope (next PRs):**
- Flute consuming inbound `geometry.cgp.v1` from other services (subscribe-side handler)
- Deprecation timeline for `tokenism.geometry.event.v1` (post-consumer-migration audit)
- #1398 chakra encoder + #1399 breath generator (independent low-cost wins)

◆ Claude Opus | #7C3AED | 2026-04-27 | Geometry Bridge (#1397) shipped — dual-publish, signed CGP v0.2, 19 tests green
Resonance: geometry-bus, dual-publish-migration, hmac-sign-verify, drift-guard
Mirror-lane: shipped per PR #1401 §3.1 / §3.2 recommendation; z890's authoring lane untouched.
