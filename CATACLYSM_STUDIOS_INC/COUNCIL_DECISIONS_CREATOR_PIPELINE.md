# Council Decisions Illustrated via Creator Pipeline

> **Status: 2026-10-10.** Every cited route was probed live (HTTP 200) on 2026-10-10; voice evidence from `research/analyses/2026-10-10_PIPECAT_REVIEW_FLUTE_INTEGRATION.md` + `plans/VOICE_LAYER_WIRING_PLAN_2026-10-10.md`. Illustration ≠ execution: these artifacts *communicate* council decisions; they never settle, mint, or execute them (settlement path: [CHIT_SETTLEMENT_PRACTICE_STATUS.md](CHIT_SETTLEMENT_PRACTICE_STATUS.md)).

Council decision types (dues ledger, voting pilot, settlement go-live, capacity expansion) are abstract until a resident sees one. The creator pipeline turns each into a shareable, verifiable artifact — already live on pmoves.ai.

| Council decision type | Illustrating artifact (live route) | What it shows | Pipeline stage |
|---|---|---|---|
| **Dues ledger** | `/tenant-template/` (200) — tenant-page render | Per-unit dues, contributions, and ledger readout in the resident-facing page a tenant board would actually publish | Render |
| **Voting pilot** | `/stage/` (200) + `/persona/` (200) | Room-and-stage framing of the pilot: rehearsal-stage rooms, persona briefs, one-resident-one-vote messaging | Render |
| **Settlement go-live** | `/chit-tour/` (200) | CHIT Geometry Bus walk-through: signed attestations → attribution → (gated) settlement; keeps MEASURED vs GATED labels strict | Render + embed |
| **Capacity expansion** | `/hyperdim/` (200) | Hyperdimensional visualization of pooled mesh capacity growth — the visual argument for adding nodes | Render + embed |
| **All of the above** | `/embeds/beats-constellation/` (200) | Embeddable beats-constellation widget — drop any decision's data view into docs, decks, or the tenant page | Embed |

**Voice announcements (OmniVoice).** Decision notices and go-live announcements render through the OmniVoice voice pool. MEASURED (2026-10-05): Flute-Gateway :8055 up with `/v1/voice/config` reporting providers (vibevoice, whisper, elevenlabs, ultimate_tts, voicebox, omnivoice) and **omnivoice as default**; personas on. Placement per wiring plan: host = OmniVoice/UTTS batch synth, 5090 = vibevoice-realtime + voice-relay, SPARK = realtime RTVI/WebRTC edge.

**Boundary (illustration vs execution):** a render, embed, or announcement is creator-pipeline output. It may illustrate a decided item or a pending proposal, but ledger writes only happen on the production settlement path, votes only in the (gated) ballot apps — never in these surfaces.

**Next wave (designed, not live):** RTVI v1.0.0 browser ingress for room-voice announcements and SmallWebRTCTransport per the PIPECAT review §4 — sequencing voice-router → RTVI/WebRTC → telephony.
