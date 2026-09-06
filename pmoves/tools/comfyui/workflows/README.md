# MiniMax H3 ULTRA ComfyUI Workflows

Two exported ComfyUI workflow JSONs from the Aitrepreneur MiniMax H3 ULTRA
setup. Drop them into ComfyUI's workflow load dialog (or use the
`/prompt` API endpoint with the same JSON) and they run as-is once the
install scripts in `../install/` have finished downloading the model
files.

## Which workflow do I use?

| Workflow | When to use | Render time (RTX 4090, 5s 720p) |
|----------|-------------|----------------------------------|
| `MINIMAX_H3_ULTRA_+TURBO-LORA_WORKFLOW.json` | **Default** - fast iteration, concept work, skin renders, storyboards. 4-step sampling. | ~30-60s |
| `MINIMAX_H3_ULTRA_WORKFLOW.json` | Final renders, hero shots, music video clips. Full quality sampler chain. | ~3-5min |

The Mavis client (`comfyui_client.py`) defaults to the **turbo-LoRA** workflow
because Pillar 4 skin renders and beat-to-room stills prioritize iteration
speed. Set `PMOVES_COMFYUI_WORKFLOW=...` to override per-render.

## What's in each workflow

Both workflows wire the same 6-model H3 ULTRA stack:

- **Text encoder:** `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` (Qwen3-VL 32B)
- **FL2VA diffusion** (T2V + I2V): `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- **REF2VA diffusion** (reference video): `minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- **Video VAE:** `minimax_h3_video_vae_fp16.safetensors`
- **Audio VAE:** `minimax_h3_audio_vae_fp32.safetensors`
- **Turbo LoRA** (turbo workflow only): `minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors`

Both produce 5-second video clips at 720p height (default width follows aspect
ratio). The variable inputs (`SEED`, `HEIGHT`, `Video Duration (in seconds)`)
are exposed as `INTConstant` / `RandomNoise` / `PrimitiveFloat` nodes so the
Mavis render_skin.py can override them per call.

## Custom node required

Both workflows require `ComfyUI-Spectrum-MiniMax-H3` (cloned from
`xmarre/ComfyUI-Spectrum-MiniMax-H3`). The install scripts in `../install/`
add it to `custom_nodes/` automatically. If you're loading these workflows
into a ComfyUI host that doesn't have that custom node, the workflow will
fail with "node type not found" on the `b7d2ab76-9af5-45f9-b51c-8451c0ee0d7e`
node (a custom sampler patch).

## Editing the workflows

The workflow JSONs are exported by ComfyUI and have the full node graph
(id, type, position, inputs/outputs, widget_values, links). To customize:

1. Open ComfyUI in a browser
2. Drag the JSON into the workflow editor
3. Edit the nodes you want (typically the `CLIPTextEncode` for prompts, the
   `LoadImage` for sketch input, or the `INTConstant` for HEIGHT/SEED)
4. Save the API-format JSON (the "Save (API Format)" button, not "Save")
5. Point `PMOVES_COMFYUI_WORKFLOW` at the new file

The Mavis `render_skin.py` is designed to be workflow-agnostic: it reads
`inputs` (the `SetNode` / `GetNode` / `LoadImage` / `CLIPTextEncode` widgets)
and sets the prompt + sketch via the standard `workflow_api` format, so any
H3-ULTRA-compatible workflow will work without code changes.

## Why these specific workflows

The Aitrepreneur workflows are the only public exports of MiniMax H3 ULTRA
that:

- Use the full 6-model stack (most public H3 workflows drop the audio VAE
  or the turbo LoRA)
- Are exported in API format (most public exports are UI format, which
  ComfyUI's `/prompt` endpoint rejects)
- Pin the sampler chain via the Spectrum custom node (gives consistent
  results across machines)

The downside is they're large (~250KB each) and versioned to a specific
ComfyUI build (0.30.0 for the turbo, 0.29.0+ for the standard). If you
upgrade ComfyUI, re-export the workflow from a working install to get
the new node IDs.

## V3 workflows (added 2026-09-06)

`MINIMAX_H3_ULTRA_WORKFLOW-V3.json` + `MINIMAX_H3_ULTRA_TURBO_WORKFLOW-V3.json`
— production pipeline: 356 nodes, 11-stage sampling, 12 resolution selectors,
SageAttention patched at 11 sites (`PathchSageAttentionKJ` — needs the
SageAttention install from `../install/OPTIONAL_SAGEATTENTION-INSTALLER.bat`
on Windows hosts, or the Linux equivalent on SPARK).

V3 model manifest (8 files, superset of V1's 6):

| model | role |
|---|---|
| `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | text encoder (int8) |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | T2V/I2V engine (int8) |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | reference-video engine (int8) |
| `minimax_h3_video_vae_fp16.safetensors` | video VAE |
| `minimax_h3_audio_vae_fp32.safetensors` | audio VAE (new in V3) |
| `minimax_h3_t1_image_vae_step1597.safetensors` | image VAE |
| `minimax_h3_latent_upscaler_3d_fp16.safetensors` | 3D latent upscaler (new in V3) |
| `sam3.1_multiplex_fp16.safetensors` | SAM 3.1 subject segmentation (new in V3) |

Custom-node stack beyond V1's Spectrum node: rgthree (Power Lora Loader, Fast
Groups Bypasser), VHS VideoCombine, KJ-nodes (SageAttention patch),
MiniMaxH3SigmaShift / MediaLoader, ResolutionSelector.

## SPARK stage-1 result (measured 2026-09-06): SageAttention runs on GB10

The unlock is one environment variable — Triton 3.5.1 ships a `ptxas` that
predates `sm_121a`, and the kernel JIT dies with
`ptxas fatal: Value 'sm_121a' is not defined for option 'gpu-name'`.
The host's CUDA 13.0 toolkit knows the arch:

```bash
export TRITON_PTXAS_PATH=/usr/local/cuda-13.0/bin/ptxas
```

Probe (autoresearch venv, torch 2.9.1+cu128, triton 3.5.1, pip
`sageattention`): `sageattn(q,k,v, tensor_core=True, pv_accum_dtype="fp16+fp32")`
executed with mean abs diff **0.00053** vs SDPA reference — numerically PASS.
At the tiny probe shape (1×16×1024×128) sageattn is not yet faster than SDPA
(0.16 vs 0.12 ms — quant overhead dominates); the payoff arrives at video-gen
sequence lengths, which is what the H3 V3 pipeline feeds it. Any SPARK
ComfyUI/serving container that wants the 11 SageAttention patch sites must
export `TRITON_PTXAS_PATH` (or carry CUDA 13 ptxas) — same lesson class as
the #2871 torch-cu128 preinstall.
