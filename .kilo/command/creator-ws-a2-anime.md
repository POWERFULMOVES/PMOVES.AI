# creator-ws-a2-anime

Field brief for **KiloCode (GLM-5.1 / 5090)** — implement WS-A2 (anime / character
personas) of the creator pipeline. Three-Body: 4090-CLAUDE analyzed + scaffolded
the ComfyUI self-host config; KiloCode executes the GPU build, LoRA training, and
workflow wiring; trail signed on completion (`chit:sign-trail`).

Source plan: `research/CREATOR_PIPELINE_HANDOFF_2026-06-08.md` (WS-A2) +
`pmoves/docs/handoffs/creator-comfyui-selfhost-config-2026-06-24.md`.

## Arguments

- `model` (string, default `animagine-xl-4`): `cagliostrolab/animagine-xl-4.0`
  (**OpenRAIL++** — commercial-permitted; honor the use-restrictions; record the
  compliance note). Danbooru-tag native, SDXL base, broad ControlNet/LoRA support.
  **Never ANIMA (non-commercial) or any NC model.**
- `character` (string, required): persona to train/render — the FlOO$ cast
  (dr-bean / mr-clean / powerpuff-*) or DARKXSIDE aesthetic.
- `comfyui_url` (string, default `${COMFYUI_URL:-http://comfyui:8188}`).
- `train_lora` (bool, default true): train a per-character LoRA (ANIMA video used
  the Citron trainer; use a license-clean trainer).

## Implementation

1. **Reuse the ComfyUI runtime** from WS-I (`creator-ws-i-images` brief) — same
   self-host build on :8188; do not stand up a second ComfyUI.
2. **Install Animagine-XL-4.0** (OpenRAIL++) into `comfyui-models`; record model id
   + license + use-restriction note (license gate).
3. **Danbooru-tag + natural-language workflow** with inpainting ControlNet. Adapt an
   existing graph under `pmoves/creator/workflows/` where possible; export the POST
   `/prompt` API JSON to `pmoves/services/comfyui/prompt_examples/`.
4. **Per-character LoRA training** (`train_lora=true`): small dataset → LoRA on the
   5090; store the LoRA in `comfyui-models/loras`; tag each LoRA with character +
   source-license provenance. Use a license-clean trainer (verify before adopting).
5. **Emit CGP provenance** per artifact (model, LoRA, license, prompt hash, optional
   cymatic glyph). Outputs → comfy-watcher → MinIO `pmoves-comfyui` + NATS (existing
   seam). Bind personas via the `persona-bind` skill so anime art + voice (OmniVoice)
   share the same FlOO$ character identity.
6. **Smoke**: render one FlOO$ character with its trained LoRA; verify artifact in
   MinIO + NATS and the CGP `point.meta` carries the LoRA + license.

Files:
- `pmoves/services/comfyui/prompt_examples/` — exported anime + LoRA graphs.
- `pmoves/config/creator_models.yaml` — register Animagine-XL-4 + each LoRA + license.
- `.claude/skills/persona-bind/` — character suit ↔ voice/art binding.

## Related

- `pmoves/docs/handoffs/creator-comfyui-selfhost-config-2026-06-24.md` — ComfyUI runtime decision
- `.kilo/command/creator-ws-i-images.md` — shares the ComfyUI runtime + CGP/MinIO seam
- `pmoves/creator/tutorials/mumpitz.md` — LoRA-training tutorial (ignore its RunPod section)
- `reference_creator_pipeline_models` (memory) — license verdicts: Animagine-XL-4 ADOPT, ANIMA REJECT
- `project_cinco_de_mayo_launch` (memory) — FlOO$ persona cast context

## Notes

- **License gate is hard:** Animagine-XL-4.0 is OpenRAIL++ (commercial-permitted with
  use-restrictions) — acceptable WITH a compliance note in CGP `point.meta`. Verify the
  SDXL base + any LoRA-trainer license also permit commercial use.
- LoRA datasets must be rights-clean (own/licensed source art only).
- GPU build + training validate on-node (5090); CI doesn't build GPU images.
- Close the loop with `chit:sign-trail` referencing this brief.
