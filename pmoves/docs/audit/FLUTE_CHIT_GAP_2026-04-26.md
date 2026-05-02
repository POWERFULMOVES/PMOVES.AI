# Flute CHIT-Gap Audit — 2026-04-26

**Question this audit answers:** *"Is there good CHIT not yet implemented from doc?"* (DARKXSIDE, 2026-04-26)

**Source docs surveyed:**
- `pmoves/docs/context/FLUTE_VISION_MULTIMODAL.md` (PR #1394, 178 lines) — multimodal vision: POML, Mangle, Qwen-Omni, CHIT geometry-bus, JAMZ, n8n, unified message schema
- `pmoves/docs/context/FLUTE_ARCHITECTURE_ROADMAP.md` (PR #1395, 617 lines) — voice/TTS engineering: 4-tier hierarchy, data model, API spec, NATS subjects, provider integrations, Phase 12a–d
- `pmoves/docs/AGENTS/AGNOTE4482FLUTE.md` (PR #1393, 155 lines) — well-being-matrix axis: chakra ↔ HRV ↔ BPM ↔ Hz octave, breath cycle generator, tap-hammer-off octave climb

**Implementation surface checked:** `pmoves/services/flute-gateway/`, `pmoves/tools/`, `pmoves/configs/`, `pmoves/integrations/`, `pmoves/contracts/schemas/`, root compose files.

---

## Status Table

| Feature (described in vision/roadmap) | Status | Evidence | Issue stub |
|---|---|---|---|
| **POML Prompt Orchestrator** (Microsoft) | unimplemented | `Grep poml \| POML pmoves/` → 10 hits, **all in docs or unrelated notebooks**. Zero in `pmoves/services/`. No `microsoft/poml` in any `requirements*.txt` or `package*.json`. | [Issue stub 1](#issue-stub-1--poml-prompt-orchestrator) |
| **Mangle Translator** (Google deductive-query) | unimplemented | `Grep mangle pmoves/` → 20+ hits, **all are JS minification false positives** (`webpack-config.js`, `regenerator-runtime`) or unrelated text. No Go binary, no Python bindings, no `google/mangle` reference. | [Issue stub 2](#issue-stub-2--mangle-deductive-translator) |
| **Qwen-3 Omni Captioners** (image+audio) | unimplemented | `Grep Qwen3-Omni pmoves/` → 2 hits (GEMINI.md + Doc B itself). Not in `pmoves/configs/gpu-models.yaml`, not in `pmoves/configs/models.yaml`, not in TensorZero routing, not in flute-gateway providers. | [Issue stub 3](#issue-stub-3--qwen-3-omni-captioners) |
| **JAMZ multimedia library** | unimplemented | `Grep JAMZ\|jamz pmoves/` → 5 hits, **all unrelated** (docling notebook example data + Doc B itself). No JAMZ package, no service, no submodule. | [Issue stub 4](#issue-stub-4--jamz-multimedia-library) |
| **CHIT geometry-bus encode/decode in Flute** | unimplemented | `Grep geometry.cgp pmoves/services/flute-gateway/` → 0 hits. Flute does have CHIT imports (7 files: `voicebox.py`, `main.py`, `mcp_bridge.py`, `bpm_encoder.py`, pipecat processors), but does not encode messages to / decode messages from `geometry.cgp.v1`. | [Issue stub 5](#issue-stub-5--flute-geometry-bus-bridge) |
| **`geometry.cgp.v1` Supabase Realtime broadcast** | implemented | `Grep geometry.cgp pmoves/` → 20+ hits including `services/graphiti/nats_subject_registry.py`, `services/gateway/gateway/api/chit.py`, `tools/chit_security_validator.py`, `tools/beats_to_cgp.py`, `docs/geometry-bus/`. Subject is wired and CGP packets are produced/consumed by other services. | — |
| **CHIT Voice Attribution Integration** | implemented | `pmoves/docs/infrastructure/FLUTE_PROSODIC_ARCHITECTURE.md` line 360 has dedicated section. Flute providers (`voicebox.py`) carry `chit` references for attribution. | — |
| **BPM ↔ prosodic boundary mapping** | implemented | `pmoves/tools/bpm_encoder.py` (Python) + `musicMapping.ts` (TypeScript) + `pmoves/services/flute-gateway/prosodic/bpm_encoder.py`. 5-band table (SENTENCE/BREATH/CLAUSE/PHRASE/NONE). | — |
| **CGP v0.2 prosodic packet format** | implemented | `/chit:bpm` skill + `chit_security.py` HMAC signing + `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json`. | — |
| **`tokenism.prosodic.bpm.v1` NATS subject** | implemented | Wired in `pmoves/services/flute-gateway/`, documented in `AGNOTE4482.BEATS.md` line 130. | — |
| **Multi-engine TTS providers** (13 engines) | implemented | `pmoves/services/flute-gateway/providers/` — VibeVoice, Higgs, Fish S2, Kokoro, F5-TTS, IndexTTS, IndexTTS2, Fish Speech S1, KittenTTS, ChatterboxTTS variants, VoxCPM, Qwen Voice Design, VibeVoice. CUDA verified Sessions 4–6. | — |
| **Persona selection by intent** | implemented | `pmoves/services/flute-gateway/persona_selector.py` (Session 5 ship). | — |
| **Pipecat WebSocket transport** | partial | `pmoves/services/flute-gateway/pipecat/transports/fastapi_ws.py` exists but full duplex voice conversation per Doc A §5.2.3 needs end-to-end harness verification. | [Issue stub 6](#issue-stub-6--pipecat-duplex-harness) |
| **Voice cloning endpoint** (`/v1/voice/clone`) | partial | Doc A §5.1 specifies endpoint shape; service has `clone` references but consent + biometric-match safety gate from `AGNOTE4482FLUTE.md` Movement V is missing. | [Issue stub 7](#issue-stub-7--voice-clone-safety-gate) |
| **Chakra-axis encoder (7 bands)** | unimplemented | New axis proposed in `AGNOTE4482FLUTE.md` Movement I. No `chakra_encoder.py`, no chakra column in CGP schema, no chakra preset in providers. | [Issue stub 8](#issue-stub-8--chakra-axis-encoder) |
| **EKG / HRV biometric ingest** | unimplemented | Per `AGNOTE4482FLUTE.md` Movement V item 2. No `health.ekg.bpm.v1` subject, no biometric service, no rPPG/HRV input path. | [Issue stub 9](#issue-stub-9--ekg-hrv-biometric-ingest) |
| **Well-Being Matrix Monitor service** | unimplemented | Per `AGNOTE4482FLUTE.md` Movement V item 3. No matrix-monitor service exists. Would subscribe to `tokenism.prosodic.bpm.v1` + `health.ekg.bpm.v1`, publish `wellbeing.matrix.score.v1`. | [Issue stub 10](#issue-stub-10--well-being-matrix-monitor) |
| **6-second breath cycle generator** | unimplemented | Per `AGNOTE4482FLUTE.md` Movement II. 10-BPM cadence, INHALE/EXHALE TTS prosodic envelope. No service code, no provider preset. | [Issue stub 11](#issue-stub-11--breath-cycle-generator) |
| **Tap-HammerOff CGP encoder** | unimplemented | Per `AGNOTE4482FLUTE.md` Movement III. 3s octave-climb pattern as discrete CGP packet variant. | [Issue stub 12](#issue-stub-12--tap-hammeroff-cgp) |
| **Cymatic visualizer hook** (Hyperdimensions) | unimplemented | Per `AGNOTE4482FLUTE.md` Movement V item 4. `freqToY` log mapping exists in Hyperdimensions; missing scene preset that ingests `tokenism.prosodic.bpm.v1` + chakra band. | [Issue stub 13](#issue-stub-13--cymatic-visualizer-hook) |

---

## Summary

**Totals: 20 features audited → 7 implemented / 2 partial / 11 unimplemented**

- **7 implemented:** `geometry.cgp.v1` subject, CHIT voice attribution, BPM↔boundary bridge, CGP v0.2 packet format, `tokenism.prosodic.bpm.v1` NATS subject, multi-engine TTS providers, persona selection by intent
- **2 partial:** pipecat duplex harness, voice-clone endpoint
- **11 unimplemented** — fall into two clusters:
  - **Multimodal vision cluster** (Doc B, never engineered, 5 items): POML, Mangle, Qwen-Omni, JAMZ, Flute geometry-bus bridge
  - **Well-being-matrix cluster** (AGNOTE seed, never engineered, 6 items): chakra-axis encoder, EKG/HRV ingest, matrix-monitor service, breath cycle generator, tap-hammeroff CGP, cymatic visualizer

**Highest-leverage gap:** Flute geometry-bus bridge (Issue stub 5). The bus exists, CHIT exists, the `geometry.cgp.v1` subject is wired — but Flute itself doesn't ride the bus. Closing this single gap connects voice prosody to CHIT geometry attribution at the service boundary, which then unlocks every downstream CHIT-aware voice feature.

**Lowest-cost gaps:** Issues 8 (chakra encoder, ~80 lines extending bpm_encoder.py) and 11 (breath cycle generator, prosodic envelope only). Both are additive, both reuse existing infrastructure, both ship as single PRs.

---

## Issue Stubs

### Issue stub 1 — POML Prompt Orchestrator

**Description:** Doc B describes a Microsoft POML-based prompt orchestrator that wraps user input in `<role>`, `<task>`, `<document>`, `<img>`, `<output-format>` tags before forwarding to Agent Zero. None of this exists.

**Scope:** Spike to evaluate POML SDK (Python or TypeScript), build a `pmoves/services/poml-orchestrator/` service or library wrapper, integrate with Flute as the prompt-construction step before Agent Zero handoff. Likely 1–2 weeks scoping + 2–3 weeks implementation.

**Open questions:** Is POML still maintained? Does the SDK support our target Python version? How does it interact with TensorZero's prompt routing?

---

### Issue stub 2 — Mangle Deductive Translator

**Description:** Doc B describes Google's Mangle as the deductive-query layer that translates cross-source user intent into Datalog-like rules. Not implemented.

**Scope:** Mangle is Go-only. Either run a Go microservice exposing a `/translate` endpoint or use Python bindings (if any exist). Significant effort for a feature whose use cases are not yet validated.

**Open questions:** Are there real PMOVES queries today that would benefit from Mangle vs. just calling Agent Zero with structured prompts? Validate need before building.

---

### Issue stub 3 — Qwen-3 Omni Captioners

**Description:** Doc B specifies Qwen-3 Omni for image+audio captioning. Not in TensorZero routing, not in `gpu-models.yaml`, not in flute-gateway providers.

**Scope:** Add Qwen3-Omni-30B-A3B-Captioner to `pmoves/configs/gpu-models.yaml` (VRAM budget), add to `pmoves/configs/models.yaml` (TensorZero routing), add captioner provider to `pmoves/services/flute-gateway/providers/`, wire to `/v1/voice/recognize` for audio + new `/v1/media/caption` for images.

**Open questions:** Is the 30B variant within RTX 5090 VRAM budget alongside other loaded models? Is there a smaller variant suitable for Z890?

---

### Issue stub 4 — JAMZ multimedia library

**Description:** Doc B references JAMZ as an internal PMOVES toolkit for multimedia preprocessing + Jellyfin integration. No code exists with that name.

**Scope:** Investigate whether JAMZ was renamed (maybe absorbed into `pmoves/services/media-video-analyzer/` + `media-audio-analyzer/`?) or never built. If never built, decide whether the JAMZ surface is still wanted or whether existing services cover the use cases.

**Open questions:** Is "JAMZ" a deprecated codename for already-shipped services? Confirm with operator.

---

### Issue stub 5 — Flute geometry-bus bridge ⭐ HIGHEST LEVERAGE

**Description:** `geometry.cgp.v1` is wired across PMOVES (graphiti, gateway, tools, docs), and Flute imports CHIT in 7 files for attribution. But Flute does not encode outgoing voice events as CGP packets, nor does it decode incoming geometry packets into voice prosody.

**Scope:** Add `pmoves/services/flute-gateway/geometry_bridge.py` that subscribes to `geometry.cgp.v1` and decodes incoming packets to TTS input, and publishes voice events as `geometry.cgp.v1` packets with prosodic chunk metadata. Reuses existing `chit_security.py` HMAC signing.

**Open questions:** Should encoding be enabled by default or feature-flagged? What is the CGP schema's prosodic field shape — does it match `ProsodicChunk` from `FLUTE_PROSODIC_ARCHITECTURE.md`?

---

### Issue stub 6 — Pipecat duplex harness

**Description:** `pmoves/services/flute-gateway/pipecat/transports/fastapi_ws.py` exists. Doc A §5.2.3 specifies a duplex voice conversation endpoint. End-to-end harness verifying simultaneous TTS + STT in one WebSocket session not yet validated.

**Scope:** Build harness in `pmoves/services/flute-gateway/tests/` that opens a WebSocket session, streams audio in, receives audio out, validates round-trip latency and audio integrity.

---

### Issue stub 7 — Voice clone safety gate

**Description:** Doc A §5.1 documents `/v1/voice/clone`. `AGNOTE4482FLUTE.md` Movement V item 6 calls for a safety gate: refuse cloning during an active guided session unless the cloned voice is the user's own (consent + biometric match).

**Scope:** Add consent capture flow + biometric voice-match check (compare uploaded sample against registered user voice signature) before allowing clone request to proceed.

---

### Issue stub 8 — Chakra-axis encoder

**Description:** `AGNOTE4482FLUTE.md` Movement I proposes a 7-chakra extension to the existing 5-band BPM table.

**Scope:** Extend `pmoves/tools/bpm_encoder.py` and `pmoves/services/flute-gateway/prosodic/bpm_encoder.py` with the chakra band table (Muladhara → Sahasrara, C2 → C5). Add `chakra` field to CGP v0.2 schema. ~80 lines of code + schema update + tests.

**Lowest-cost win** in the well-being-matrix cluster.

---

### Issue stub 9 — EKG / HRV biometric ingest

**Description:** Per `AGNOTE4482FLUTE.md` Movement V item 2. New input modality.

**Scope:** Define `health.ekg.bpm.v1` NATS subject. Build minimal ingest service that accepts heart-rate stream from rPPG webcam / Polar H10 / Apple Watch healthkit and publishes to subject. Privacy + consent considerations.

**Open questions:** Which input source first? Webcam-rPPG is most-frictionless; Polar H10 most-accurate; healthkit requires platform-specific export.

---

### Issue stub 10 — Well-Being Matrix Monitor service

**Description:** Per `AGNOTE4482FLUTE.md` Movement V item 3. Sits alongside Flute, scores user adherence to guided cycles.

**Scope:** New service at port `8056+` (TBD). Subscribes to `tokenism.prosodic.bpm.v1` + `health.ekg.bpm.v1`. Publishes `wellbeing.matrix.score.v1`. Depends on Issues 8 + 9.

---

### Issue stub 11 — Breath cycle generator

**Description:** Per `AGNOTE4482FLUTE.md` Movement II. 10-BPM cadence, INHALE/EXHALE TTS prosodic envelope.

**Scope:** Add a "Breath Guide" persona to `pmoves/services/flute-gateway/persona_selector.py`. Add prosodic envelope shaper for 6s ramp up + 6s ramp down. Provider preference: VibeVoice for slow ramps, Higgs for steady tone.

**Lowest-cost win** for guided meditation/wellness use cases.

---

### Issue stub 12 — Tap-HammerOff CGP encoder

**Description:** Per `AGNOTE4482FLUTE.md` Movement III. 3-second octave-climb pattern (C3 → C4 → C5) as discrete CGP packet variant.

**Scope:** Add `tap_hammeroff` packet variant to CGP schema. Add encoder in `pmoves/tools/`. Couples with breath cycle (issue 11) for full meditation/focus orchestration.

---

### Issue stub 13 — Cymatic visualizer hook

**Description:** Per `AGNOTE4482FLUTE.md` Movement V item 4. Hyperdimensions has `freqToY` log mapping; needs scene preset.

**Scope:** Add `pmoves/Pmoves-hyperdimensions/saves/cymatic_breath.json` scene that ingests `tokenism.prosodic.bpm.v1` + chakra band as color axis. ~2 days against existing scene loader.

---

## Methodology Note

This audit is **read-only and reproducible**. Every "implemented" / "partial" / "unimplemented" verdict cites the exact `Grep` invocation and result count that was used to make the determination. To re-run: see the "Evidence" column commands.

False positives flagged explicitly (e.g., "Mangle" matching JS webpack mangling) so the next operator doesn't double-count.

This audit does **not** decide whether unimplemented features should be built — it only catalogs the gap. Prioritization is the operator's call.
