---
name: comfy-operate-image
description: >
  Drive the real ComfyUI UI to run the Ideogram-Ultra image workflow via the
  chrome-devtools MCP, narrating each knob to teach the user, and harvest the
  POST /prompt API-format payload. Used by the creator-operator (L1). The end
  user never touches the node graph.
---

# comfy-operate-image — Computer-Use ComfyUI Operator (image)

Drives a Pinokio-launched PMOVES-Creator ComfyUI to run **image.ideogram-ultra**.
Teaching is the feature: narrate what each knob does as you set it.

## Inputs (from the work-order)
`knobs`: `prompt` (str), `seed` (int), `input_image` (path|null). The exposed
knobs + their teaching sentences are in `knobs.json` (the single source of truth;
the completeness test asserts every exposed knob has a sentence).

## Run-book (chrome-devtools MCP)
1. `navigate_page` to the ComfyUI URL captured by the Pinokio `start.js`.
2. `take_snapshot` to anchor the UI; load the Ideogram-Ultra workflow (drag the
   saved JSON, or use the Workflow menu → Open).
3. For each exposed knob, set its widget (`fill`/`evaluate_script`) and **narrate**
   the matching `knobs.json` sentence into the transcript (`record_step`).
4. Click **Queue Prompt**.
5. `list_network_requests` → find `POST /prompt`; `get_network_request` → save the
   request body as `api_prompt` (the harvested API-format graph).
6. Poll `GET /history/{prompt_id}` until the output node reports an image; fetch it.
7. Call `assemble_result(workorder_id, artifact=..., api_prompt=..., transcript=...)`
   and hand the result to the creator-operator fan-out.

## Failure handling
- Selector/node missing → `assemble_result(..., artifact=None, api_prompt=None,
  error="<step>: <what was expected>")`. Fail closed — no partial artifact.
- ComfyUI `/history` reports a node error → surface the Comfy error text in `error`.
- `POST /prompt` not captured → still return the artifact; set `api_prompt=None`
  (the fan-out flags `has_api_prompt:false`). The run is valid; replay isn't.

## License
`image.ideogram-ultra` runs on **local** fp8 weights (`Comfy-Org/Ideogram-4`,
downloaded to the node) — no API key. Its HF license is `other` (custom), which is
**not confirmed commercial-OK**, so the creator-operator L3 gate still refuses to
dispatch unless `license_ack.ack` is true (try-locally / BYO at the user's edge —
"local" is not "commercial-OK"). For any hosted/commercial path, swap to the
license-clean `Qwen/Qwen-Image` (Apache-2.0) — see `creator_models.yaml`.
