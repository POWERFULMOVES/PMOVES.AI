# Creator Pipeline — Handoff / RFC (2026-06-08)

Open call for agents to pitch & claim workstreams. The website surface (A2UI,
Z890) is coming up, so the creator pipeline now needs its voice/image/anime
layers alongside the audio-grounding layer 4090 already shipped. This doc
captures three new **workflows** (from creator-tooling videos) with
**license-vetted** model choices, and frames each as a claimable workstream.

Companion: `research/Z890_HANDOFF_FLEET_SYNC_2026-06-08.md` (fleet sync),
`docs/superpowers/specs/2026-06-0{3,8}-ws-a-*.md` (audio grounding + cymatics).

## Pipeline shape

```
audio  ── WS-A grounding (librosa+CLAP -> CGP geometry) ── DONE ✅ (+ cymatic glyph)
voice  ── agent/persona TTS ───────────────────────────── NEW  (OmniVoice)
image  ── thumbnails/posters/branding/CGP viz ─────────── NEW  (Qwen-Image/FLUX)
anime  ── character personas / DARKXSIDE aesthetic ─────── NEW  (Animagine-XL-4)
                         │
                 CGP (geometry + attribution)  ── common substrate
                         │
                 A2UI website surface (Z890)   ── where it all lands
render engine: ComfyUI (local, open) impedance-matched to fleet GPUs
```

## The license gate (decisive — re-stated because it bit here)

Models/deps must be **truly open-source & commercial-OK** (Apache/MIT/BSD/CC-BY;
OpenRAIL's commercial-permitted-with-use-restrictions is acceptable with a
compliance note). **Never CC-BY-NC or any "non-commercial" model.** "Open-weight"
≠ commercial-OK. Verified 2026-06-08:

| From the videos | License | Verdict |
|---|---|---|
| **OmniVoice** (k2-fsa) | **Apache-2.0** | ✅ ADOPT |
| Ideogram 4 (ideogram-ai) | **Non-Commercial** Model Agreement (commercial = paid license) | ❌ REJECT — mine the workflow, swap the model |
| ANIMA 1.0 (circlestone-labs) | **Non-Commercial** (+ NVIDIA Cosmos-Predict2 derivative terms) | ❌ REJECT — mine the workflow, swap the model |

The **workflows** are model-agnostic; we keep them and substitute license-clean
models below.

## Workstreams (pitch & claim)

### WS-V — Voice for agents  *(ADOPT)*
- **Model:** OmniVoice (`k2-fsa/OmniVoice`, **Apache-2.0**) — zero-shot voice
  cloning + voice design, 600+ languages, ~40x real-time, ComfyUI node
  (`Saganaki22/ComfyUI-OmniVoice-TTS`).
- **Integration:** the voice tier for the FlOO$ persona system (Dr. Bean /
  Mr. Clean / PowerPuff) and Flute voice-first; local on the fleet (no
  ElevenLabs spend). Pairs with the `persona-bind` skill + `shift-from-bpm`
  (BPM-prosody) — voice prosody can ride the WS-A beats/tempo features.
- **First task:** stand up an OmniVoice service (clap-embed pattern: FastAPI
  `/clone` + `/tts`, injectable model, `/healthz /metrics`), license-tagged in
  the model registry; wire to Flute-Gateway.

### WS-I — Images  *(workflow ✅ / model swapped)*
- **Workflow (from the Ideogram-4 video):** ComfyUI **area-prompting / regional
  control**, perfect text rendering, posters / thumbnails / logos.
- **Model (license-clean):** **Qwen-Image** (`Qwen/Qwen-Image`, **Apache-2.0**)
  — strong text rendering + **ControlNet-Inpainting** (the regional-control
  equivalent); or **FLUX.1-schnell** (`black-forest-labs/FLUX.1-schnell`,
  **Apache-2.0**) for fast drafts. Ideogram-4 rejected (NC).
- **Integration:** website thumbnails/hero art/branding (Z890), marketing
  assets, and **CGP/cymatic-glyph compositing** (overlay the audio glyph on
  generated art).

### WS-A2 — Anime  *(workflow ✅ / model swapped)*
- **Workflow (from the ANIMA video):** small fast model, **Danbooru tags +
  natural language**, **inpainting controlnet**, **LoRA training** (the video
  uses Citron LoRA trainer) — train per-character LoRAs.
- **Model (license-clean):** **Animagine-XL-4.0**
  (`cagliostrolab/animagine-xl-4.0`, **OpenRAIL++** — commercial-permitted, honor
  the use-restrictions) — Danbooru-tag native, SDXL base, broad ControlNet/LoRA
  ecosystem. ANIMA rejected (NC). (Verify any other anime candidates before use.)
- **Integration:** character-persona art (the FlOO$ cast), DARKXSIDE aesthetic,
  anime assets for the site/School-of-POWERFUL-MOVES content.

## Common substrate (so workstreams compose, not collide)
- **ComfyUI** = the open, local render engine for WS-I/WS-A2; impedance-match to
  fleet GPUs (5090 32GB / 4090 / Spark 128GB GB10 / Sonic Z890 24GB — see
  `project_fleet_topology_nodes`). KiloCode (GLM, 5090) implements from
  `.kilo/command/` briefs; MiniMax drives persona voice lines.
- **CGP** = the shared geometry + attribution layer; every generated artifact can
  carry a CGP point.meta (provenance, model+license, the cymatic glyph).
- **Cymatic-glyph bridge** (PR #1746): `cymatic_glyph(**glyph_params_from_features(
  point.meta.cymatic))` → an SVG the website renders, so beats visuals are driven
  by the real signal, not decorative loops. WS-I can composite it onto art.
- **A2UI / NATS** = the website surface (Z890) where voice + image + anime + glyph
  land.

## How to pitch / claim
Claim a workstream in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (Village Rule),
open a design spec under `docs/superpowers/specs/`, and follow the WS-A pattern
(deterministic tool tier + model tier, license-tagged, tests, CGP emission).
Suggested owners: **Z890** website integration, **KiloCode/5090** ComfyUI
workflows + LoRA training, **MiniMax** persona voice lines, **4090** audio/CGP
grounding + cymatic bridge.

## License-verify checklist (before ANY model enters the pipeline)
- [ ] License is Apache/MIT/BSD/CC-BY (or OpenRAIL with use-restriction note) — **never CC-BY-NC / non-commercial**.
- [ ] Record model id + license in the model registry / CGP `point.meta`.
- [ ] Confirm base-model/derivative terms (e.g. NVIDIA Cosmos, SDXL) also permit commercial use.
