# Creator Fleet + OmniVoice — Design (slice 2, 2026-06-09)

**Author:** 4090-claude · **Status:** design (approved verbally; pending spec-review)
**Builds on:** slice 1 (`2026-06-09-creator-operator-lattice-design.md`, merged PR #1757).

## Thesis

Slice 1 proved the work-order → operator-result contract on **one node, one
workflow (image)**. Slice 2 makes the **capacity routing real across the fleet**
and adds the **voice** workflow (OmniVoice) — light, Apache-2.0, fleetwide — as
the first multi-node, multi-workflow proof. "Users pick their voice + a cool anime
illustrated with Ideogram treatment, on call from 5090/SPARK/B850" is the demo;
**voice is the foothold** because it's the lightest + the only license-clean one.

The router from slice 1 already does impedance matching; slice 2 just **registers
the fleet** and **tags each workflow's capacity needs** so voice routes fleetwide,
anime to light nodes, image to 16 GB+ CUDA nodes, video to 24 GB+ CUDA nodes.

## Two deliverables

### A. Fleet capacity realization (data + router)
- **Node registry** (`pmoves/config/operator_nodes.yaml`) — the real fleet, by
  capacity class + GPU vendor. Hostnames only (no Tailscale IPs).

  | node_id | reach (hostname) | vram_gb | caps |
  |---|---|---|---|
  | 4090 | pmoves-laptop | 16 | cuda, comfyui, browser, voice |
  | 5090 | pmoves-5090 | 32 | cuda, comfyui, browser, voice |
  | spark | pmoves-spark | 128 | cuda, comfyui, browser, voice |
  | z890 | pmoves-z890 | 24 | cuda, comfyui, browser, voice |
  | knuckles | knuckles | 32 | rocm, voice |

- **Workflow → capacity map** — each workflow entry in `creator_models.yaml`
  gains a `caps: {min_vram_gb, needs: [...]}` block. The dispatcher **derives**
  `node_caps` from the workflow when a work-order omits it (work-order may still
  override). This is what makes "voice → fleetwide" automatic.

  | workflow_id | min_vram_gb | needs | routes to |
  |---|---|---|---|
  | voice.omnivoice | 4 | voice | all 5 (fleetwide) |
  | anime.anima | 6 | comfyui | 4090/5090/spark/z890 |
  | image.ideogram-ultra | 16 | cuda, comfyui | 4090/5090/spark/z890 |
  | video.ltx | 24 | cuda, comfyui | 5090/spark |

- **The `needs:[cuda]` gate is the ROCm boundary.** `select_node` already requires
  `needs ⊆ node.caps`. A `cuda`-tagged workflow can never select `knuckles`
  (which advertises `rocm`, not `cuda`) — the router refuses correctly. No new
  router code; the caps vocabulary carries it.

### B. OmniVoice WS-V (a new L1 operator shape)
- OmniVoice (`k2-fsa/OmniVoice`, **Apache-2.0** — no license gate) runs its own
  web/demo server (`omnivoice.cli.demo`, port 8001). Unlike the ComfyUI image
  operator, there's **no node graph and no `/prompt` to harvest** — the operator
  is an **API client**, not a UI-driver.
- **`voice-operator`** (a module in `pmoves/services/creator-operator/`): given a
  `voice.omnivoice` work-order, it calls an injected **OmniVoice client**
  (abstracting whether the transport is `gradio_client` or REST — validated at
  live-test) to synthesize speech, and `assemble_result(...)` with an **audio**
  artifact (`{kind:"audio", path:...}`), `api_prompt: null` (no harvest — voice
  isn't a ComfyUI graph). The contract already permits `api_prompt: null`.
- **"Users pick their voice"** = the work-order `knobs` carry `{voice_ref|voice_design, text}`; OmniVoice's zero-shot clone + voice-design are the choices. Result fans out exactly as slice 1 (NATS/CGP/Notebook/Discord) — the audio artifact + a CGP point (model=OmniVoice, license=apache-2.0, **requires_ack:false**).

## Contract changes (minimal, additive)
- `creator_models.yaml`: add `voice.omnivoice`, `anime.anima`, `video.ltx`
  entries, each with `caps: {min_vram_gb, needs}` + license (omnivoice apache-2.0
  ack:false; anima/ltx license:other ack:true). Image entry gains its `caps`.
- `dispatcher.handle_workorder`: when the work-order omits `node_caps`, derive it
  from the workflow's `caps` (lookup via the model registry); explicit `node_caps`
  still wins. New reason path unchanged (still assign/park/refuse/reject).
- Work-order schema: make `node_caps` **optional** (derivable). Keep everything
  else. (Result schema unchanged.)

## Architecture (slice 2 view)
```text
work-order (voice.omnivoice, node_caps omitted)
   │  dispatcher derives node_caps from workflow caps {min_vram_gb:4, needs:[voice]}
   ▼  router: voice ⊆ caps on ALL 5 nodes → lowest-vram satisfying → routes fleetwide
voice-operator (on the chosen node)
   │  OmniVoice client (gradio_client/REST → :8001)  →  audio artifact
   ▼
operator-result (artifact{kind:audio}, api_prompt:null, cgp_point{model:OmniVoice, license:apache-2.0})
   └─► same fan-out as slice 1 (NATS / CGP / Notebook / Discord)
```

## Error handling (same fail-closed posture)
- OmniVoice unreachable / synth error → operator returns `status:error`,
  `artifact:null`, `error:"<detail>"` (fail-closed; no partial audio).
- Unknown/unregistered workflow → `rejected` (slice-1 behavior).
- `cuda` workflow with only `knuckles` reachable → `parked` (no-capacity) — correct.
- Voice (`needs:[voice]`) is the one that reaches `knuckles` — see ROCm seam.

## Testing
- **Router (fleet):** voice routes to the lowest-vram node incl. knuckles; video
  excludes knuckles (cuda gate) and the 16 GB nodes (vram); anime reaches light
  nodes; image excludes knuckles. Deterministic, no hardware.
- **Workflow-caps derivation:** a work-order omitting `node_caps` gets the
  workflow's caps; an explicit `node_caps` overrides.
- **OmniVoice client:** unit-tested with a `FakeOmniVoiceClient` (no live server);
  asserts the voice-operator assembles a valid audio operator-result + error path.
- **Live (UI/hardware-gated, `CREATOR_VOICE_TEST=1`):** OmniVoice up on the 4090
  → a real `/tts` call returns an audio artifact; the result validates + fans out.

## Documented seams (not slice 2)
1. **OmniVoice on ROCm (Knuckles):** the installer pins CUDA 12.8; AMD needs a
   ROCm torch swap. Until validated, `knuckles` advertises `voice` but OmniVoice's
   ROCm build is a **TODO-validate seam** — NVIDIA nodes are the confirmed
   fleetwide set. (Tracked; not blocking slice 2.)
2. **anime.anima + video.ltx operators:** registered in the caps map + routable,
   but their ComfyUI operators (like image's) are later slices — slice 2 ships the
   registry entries + routing, and the **voice** operator end-to-end.
3. SPARK is ARM/GB10 — confirm the ComfyUI/OmniVoice ARM build at live-test.
4. n8n fleet pipeline, Discord intake, YT-monitor ingestion — still slice-N seams.

## License posture (unchanged)
OmniVoice = **Apache-2.0** → `requires_ack:false` (the one ungated, commercial-OK
workflow — why it's the foothold). anima/ltx/ideogram = HF `license:other` →
`requires_ack:true` (try-locally/BYO at the edge). Never bake `other`-licensed
weights into the hosted/commercial path.
