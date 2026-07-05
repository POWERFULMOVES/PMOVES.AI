# creator-operator (L3 dispatcher) — port 8120

Validates creator work-orders, capacity-routes them (impedance match) with a
license gate, and fans results out (NATS / CGP / Open-Notebook / Discord / n8n).
The UI-driving is a chrome-devtools computer-use run guided by the
`comfy-operate-image` skill (L2), launched by the Pinokio image-ideogram launcher
(L0). See `docs/superpowers/specs/2026-06-09-creator-operator-lattice-design.md`.

## Layers (this service = L3)
- **L0 launcher** — `pinokio/image-ideogram/` here is the canonical source; it is
  vendored into the `PMOVES-Creator` submodule at `installs/pinokio/image-ideogram/`
  via a separate follow-up PR (the gitlink bump is its own commit).
- **L1 operator** — chrome-devtools MCP, driven by the `comfy-operate-image` skill.
- **L2 skill** — `.claude/skills/comfy-operate-image/`.
- **L4 models** — `pmoves/config/creator_models.yaml` (license-tagged).
- **L5 attribution** — CGP point + teaching transcript (Notebook) + Discord notify.

## Voice (slice 2)
`voice.omnivoice` is a non-ComfyUI operator: `voice_operator.run_voice(workorder, client)`
calls OmniVoice (`omnivoice_client`) and returns an audio operator-result (no
`/prompt` harvest). Apache-2.0 (ungated). Routes fleetwide via `caps {min_vram_gb:4,
needs:[voice]}`. See `VOICE_ACCEPTANCE.md`. New subjects: none (reuses
`creator.operator.result.v1`).

The fleet registry (`pmoves/config/operator_nodes.yaml`) lists 4090/5090/spark/z890
(cuda) + knuckles (rocm). `needs:[cuda]` excludes the AMD node from CUDA workflows;
`needs:[voice]` reaches all. Per-workflow caps live in `creator_models.yaml`.

## NATS subjects (register in the live catalog as an operator action — see below)
- `archon.workorder.creator.v1`   (in)  — work-order from Archon / Discord intake
- `creator.operator.assigned.v1`  (out) — work-order assigned to a node
- `creator.operator.result.v1`    (out) — operator-result fan-out

> `.claude/context/nats-subjects.md` is guard-protected; register these via the
> normal catalog-update Known Road, not a direct edit.

## Run
PYTHONPATH=. python app.py   # or: uvicorn app:create_app --factory --port 8120

## Test
PYTHONPATH=. python -m pytest tests -q   # from this directory
