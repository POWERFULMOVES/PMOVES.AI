# Creator Operator Lattice — Design (2026-06-09)

**Author:** 4090-claude · **Status:** design (pending user spec-review)
**Companion:** `research/CREATOR_PIPELINE_HANDOFF_2026-06-08.md` (workstreams),
`PMOVES-Creator/installs/` (the real workflows + 1-click installers),
`docs/superpowers/specs/2026-06-0{3,8}-ws-a-*.md` (audio grounding).

## Thesis

Other users should be able to **try** the creator-pipeline workflows
(`PMOVES-Creator/installs/`: image/Ideogram-Ultra, video/LTX-2, anime/Citron-Anima
trainer, voice/OmniVoice) **without fiddling with ComfyUI** — *and learn the knobs
by watching*. We do **not** hide ComfyUI behind a reimplemented API. We drive the
**real ComfyUI UI** with a **computer-use operator agent** that follows a
tutorial-distilled **skill**, **narrates each knob to teach the user**, produces
the artifact, and **harvests the API-format prompt as a byproduct** for later
headless replay.

This plays to PMOVES strengths — multi-agent orchestration (Archon), the MOF
lattice (every node a pore; the operator and its host node are capacity-matched),
the skills system, CGP attribution, NATS — rather than around them. Most pores
already exist; the deliverable is the **contract between layers**, proven on one
node + one workflow, with the fleet-scaling seam documented.

### Why computer-use over an API converter (decision record)

- The saved workflow JSONs are **UI-format** (`nodes`/`links`/`pos`), not the
  **API-format** (`{node_id: {class_type, inputs}}`) that `POST /prompt` accepts.
  A converter would reimplement the browser's `graphToPrompt` against 330-node
  graphs with custom nodes — brittle and version-fragile.
- A computer-use agent driving the UI is **resilient** (uses the same UI the
  tutorials teach) and **educational** (the user latent-learns the knobs by
  observation — the stated goal).
- When the agent clicks **Queue Prompt**, ComfyUI itself POSTs the API-format
  graph to `/prompt`. We **sniff that request** and harvest the exact recipe. So
  we *observe* the UI→API mapping instead of *building* it — and that harvested
  recipe is what feeds the future headless server-side path. Teach-via-UI now,
  replay-via-API later, from one run.

## The field (north star) — six pluggable, capacity-matched layers

| Layer | Responsibility | Pluggable choices (capacity-matched) | Status |
|---|---|---|---|
| **L0 Substrate** | bring ComfyUI + the workflow up, 1-click | Pinokio (local/4090) · Docker (fleet) | exists |
| **L1 Operator** | drive the real ComfyUI UI; narrate knobs; harvest `/prompt` | chrome-devtools MCP · Agent Zero CU · puppeteer | exists |
| **L2 Skill** | tutorial-distilled in-UI steps + knob teaching | one `SKILL.md` per workflow (from the YT videos) | **new** |
| **L3 Orchestration** | work-order → capacity-route → dispatch operator → export run | Archon work-orders · capacity router · n8n export | exists (wire) |
| **L4 Models** | model access + local fine-tune, license-tagged | HF · Unsloth (LoRA) · local weights | exists |
| **L5 Attribution** | harvest api-prompt, CGP `point.meta`, NATS, teaching transcript | CGP · NATS · Open-Notebook | exists |

**Two existing pores wrap the field as surfaces (no contract change — they ride
the work-order/result seams):**

- **Ingestion — YouTube monitor (`yt:*`):** the same pipeline that already watches
  creator-tooling channels (Aitrepreneur-class) is the *source* of new workflows.
  A new video → transcript → an agent distills a candidate `comfy-operate-<x>`
  **L2 skill** + flags the model license. The workflow catalog **self-extends**;
  the license gate is the one human checkpoint. (Producer of L2 skills.)
- **Creator I/O — Discord (`discord:notify`/`discord:status`):** the zero-build
  front door. *Intake:* a Discord message → Archon work-order (natural language →
  `workflow_id` + knobs) — another producer of `archon.workorder.creator.v1`.
  *Delivery:* `discord:notify` posts artifact + teaching summary — another
  subscriber of `creator.operator.result.v1`. Full transcript → Open-Notebook.

Each layer is understood and tested independently against the contract below;
swapping a layer's implementation (puppeteer for chrome-devtools, Jetson for 4090)
must not change its consumers.

## The contract (the actual product)

One run is a **work-order → operator-result** transaction. Define it once; every
workflow × every capacity node re-instantiates it.

### Work-order (L3 → L1), NATS subject `archon.workorder.creator.v1`

```json
{
  "workorder_id": "wo_<uuid>",
  "workflow_id": "image.ideogram-ultra",
  "knobs": { "prompt": "...", "seed": 12345, "input_image": null },
  "node_caps": { "min_vram_gb": 8, "needs": ["comfyui", "browser"] },
  "teach": true,
  "creator_ref": "<creator-id>",
  "license_ack": { "model": "ideogram-4", "mode": "byo-api-key", "ack": true }
}
```

### Capacity routing (L3)

A **node registry** (`pmoves/config/operator_nodes.yaml`) lists capacity-class
nodes (`node_id`, `vram_gb`, `caps[]`, `reach` = Tailscale hostname). The router
selects the lowest-capacity node that satisfies `node_caps` (impedance match) and
is reachable. **Slice 1 registers one node (4090).** Jetson/SPARK/full-fleet are
later registry entries — no code change. The router *selects*; the existing
Tailscale mesh *carries* (no new networking work in this spec).

### Operator-result (L1 → L5), NATS subject `creator.operator.result.v1`

```json
{
  "workorder_id": "wo_<uuid>",
  "status": "ok | error",
  "artifact": { "kind": "image", "path": "...", "preview_url": "..." },
  "api_prompt": { /* harvested API-format graph from POST /prompt */ },
  "transcript": [ { "step": "set seed", "knob": "seed", "teaches": "..." } ],
  "cgp_point": { /* point.meta: model, license, knobs, api_prompt_ref */ },
  "error": null
}
```

The **operator I/O contract** is substrate-agnostic: any L1 implementation accepts
a work-order and returns an operator-result. chrome-devtools MCP is slice 1 because
its network-capture cleanly harvests `api_prompt`.

## First crystallization slice (what we build)

Prove the contract **end-to-end on the 4090, workflow = image (Ideogram-Ultra)**:

- **L0:** A Pinokio launcher (`PMOVES-Creator/installs/pinokio/image-ideogram/`)
  that brings up PMOVES-Creator ComfyUI and loads the Ideogram-Ultra graph. Wraps
  the existing `.bat` install steps (model/node install) into `install.js` +
  `start.js` (captures the local ComfyUI URL per the Pinokio URL-capture pattern).
- **L1:** chrome-devtools MCP operator. Navigates the ComfyUI URL, loads the
  workflow, sets `prompt`/`seed`/optional `input_image`, hits **Queue Prompt**,
  polls `/history/{id}`, fetches the output image, and captures the `POST /prompt`
  payload via `list_network_requests`/`get_network_request`.
- **L2:** `.claude/skills/comfy-operate-image/SKILL.md` — distilled from the
  Ideogram-Ultra video: the ordered in-UI steps + a **knob glossary** (what each
  exposed knob does, in one teaching sentence) the operator narrates as it sets it.
- **L3:** `pmoves/services/creator-operator/` thin dispatcher: subscribes
  `archon.workorder.creator.v1`, runs the capacity router (1 node), invokes the
  operator, publishes `creator.operator.result.v1`. Plus an **n8n export**: the
  run serialized as an importable n8n workflow node (the capacity seam, real but
  single-node).
- **L4:** `pmoves/config/creator_models.yaml` registry entry: `ideogram-ultra`
  → `{provider: api, license: non-commercial, mode: byo-api-key}` with the license
  note. (License-clean alt `Qwen/Qwen-Image` recorded as the swap-in for any
  server-side/commercial use.)
- **L5:** CGP `point.meta` emission (model, license, knobs, `api_prompt` ref);
  the **full** teaching transcript → Open-Notebook; the artifact + a short teaching
  summary → **Discord** (`discord:notify`); NATS result published.

## Data flow (slice 1)

```
Archon (work-order)
   │  archon.workorder.creator.v1
   ▼
creator-operator dispatcher
   │  capacity router → node=4090 (reachable via Tailscale)
   ▼
chrome-devtools operator  ──drives──►  real ComfyUI UI (Pinokio-launched)
   │  load workflow · set knobs (narrate) · Queue Prompt
   │  poll /history/{id} · fetch artifact
   │  sniff POST /prompt  ──►  api_prompt (harvested)
   ▼
operator-result  (artifact + api_prompt + transcript + cgp_point)
   │  creator.operator.result.v1
   ├──►  Open-Notebook  (full teaching transcript, artifact preview)
   ├──►  Discord notify (artifact + short teaching summary)
   ├──►  CGP point.meta  (provenance + harvested recipe ref)
   └──►  n8n export       (run as importable pipeline node)
```

The work-order's *source* and the result's *sinks* are abstract, so the existing
YouTube-monitor (skill ingestion) and Discord (intake/delivery) pores attach as
extra producers/subscribers without changing the contract.

## Error handling

- **Operator step failure** (selector not found / node missing in graph): operator
  returns `status:error` with the failed step + a screenshot ref; **fail-closed**
  (no partial artifact passed downstream). The skill's knob glossary is the
  recovery map (which step, what it should look like).
- **ComfyUI execution error** (`/history` reports node error): surface the Comfy
  error text in `error`; do not retry silently (no silent failures).
- **No capacity node reachable:** router returns `error: no-capacity`; work-order
  is parked, not dropped (re-dispatch when a node registers).
- **License not acked** (`license_ack.ack != true` for a BYO/NC model): refuse to
  dispatch; emit a guidance event. The gate lives at L3, before any model runs.
- **Harvest miss** (`/prompt` payload not captured): artifact still returns;
  `api_prompt: null` with a `harvest:miss` flag — the run is valid, replay just
  isn't available yet.

## Testing

- **L2 skill:** a dry "knob glossary completeness" check — every exposed input in
  the Ideogram graph has a teaching sentence (test parses the graph's input nodes
  vs the skill glossary).
- **Contract schemas:** JSON-schema validate work-order + operator-result fixtures
  (deterministic, no GPU).
- **Router:** unit tests — impedance selection (picks lowest-capacity satisfying
  node), no-capacity path, license-gate refusal.
- **Operator (integration, GPU/UI-gated):** one live run against a launched
  ComfyUI produces an artifact + a non-null `api_prompt`; marked `@requires_ui`,
  skipped in CI, run on the 4090.
- **Harvest replay (integration):** POST the harvested `api_prompt` back to
  `/prompt` headlessly → equivalent artifact (proves the byproduct is real).

## License posture (decisive)

- Surface = **try-locally, BYO at the user's edge.** The launcher runs on the
  user's hardware; the user obtains models under their own license / API account.
  Ideogram = the user's paid API key (commercial by the user). Anima/LTX local
  weights = the user's license to accept.
- **Never** bake a non-commercial model into the **hosted/commercial** PMOVES
  server-side path. The L4 registry records license + mode; the L3 gate enforces
  `license_ack` before dispatch. License-clean swaps (`Qwen/Qwen-Image`,
  `FLUX.1-schnell`, `animagine-xl-4.0`, `OmniVoice`) are recorded for any
  server-side/commercial reuse. See `reference_creator_pipeline_models`.

## Documented seams (later slices — not built here)

1. **More workflows:** LTX-2 (video), Citron/Anima (anime LoRA *training* — long
   job shape), OmniVoice (standalone web-UI shape, not a ComfyUI graph). Each is a
   new L2 skill + L4 entry; the contract is unchanged.
2. **Capacity scaling:** register Jetson / SPARK (GB10 128GB) / full fleet in
   `operator_nodes.yaml`; the router impedance-matches automatically.
3. **Archon auto-routing depth:** work-order generation from creator intent
   (natural language → workflow_id + knobs) via Archon's factory.
3a. **Discord intake:** a Discord message → Archon work-order (Discord becomes a
   zero-build front door; another producer of `archon.workorder.creator.v1`).
3b. **YouTube-monitor → auto-skill ingestion:** new creator-tooling video →
   transcript → distilled candidate `comfy-operate-<x>` L2 skill + license flag;
   human reviews the license gate. The workflow catalog self-extends.
4. **Headless replay path:** a server-side service that replays harvested
   `api_prompt`s via `/prompt` for high-volume (non-teaching) production, using
   only license-clean models.
5. **Unsloth/local-model tier:** local fine-tune (per-character LoRA) feeding the
   anime workflow; HF for model pulls.
6. **n8n fleet pipeline:** promote the single-node n8n export to a
   capacity-scaled n8n pipeline once >1 node is registered.

## Open questions (resolved)

- *Hide Comfy or drive it?* — **Drive it** (computer-use, teaching). Resolved.
- *Operator substrate?* — **chrome-devtools MCP** for slice 1; contract keeps it
  pluggable. Resolved.
- *First workflow?* — **image/Ideogram-Ultra** (fast feedback). Resolved.
- *Is L3 a stub?* — **No**, work-order + capacity router are real (one node).
  Resolved per user amendment.
- *Where does the teaching transcript live?* — **Discord** gets the artifact + a
  short teaching summary (`discord:notify`); **Open-Notebook** gets the full
  knob-by-knob transcript. Resolved.
- *Creator I/O surface?* — **Discord** (intake as a near-term seam, delivery in
  slice 1). Workflow ingestion via the existing **YouTube monitor**. Resolved.
