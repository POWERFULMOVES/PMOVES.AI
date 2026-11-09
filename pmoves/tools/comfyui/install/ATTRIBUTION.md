# Install Scripts Attribution

All three install scripts in this directory were written by **Aitrepreneur** and
shipped under the operator's local `SEAP` downloads folder. They are copied here
verbatim from the operator-supplied files (no modifications) so that future
Mavis sessions and other agents (Spark, Knuckles, 4090, etc.) can find them
without needing the operator's local `Downloads/SEAP/` path.

**Upstream sources:**

- RunPod installer: `MINIMAX_H3_ULTRA-AUTO_INSTALL-RUNPOD.sh`
- Windows portable one-click installer: `MINIMAX_H3_ULTRA-COMFYUI-MANAGER_AUTO_INSTALL.bat`
- Windows safe model/node installer: `MINIMAX_H3_ULTRA-MODELS-NODES_INSTALL.bat`

**Author:** Aitrepreneur (YouTube channel https://www.youtube.com/@Aitrepreneur,
170K subscribers). The installer scripts are part of the Aitrepreneur MiniMax
H3 ULTRA V1 setup, which targets the **MiniMax H3 ULTRA** model (text-to-video
+ image-to-video + reference video + audio VAE + turbo LoRA) from the
`Aitrepreneur/FLX` HuggingFace repo.

**Model provenance:**

- Upstream model: `Aitrepreneur/FLX` on HuggingFace
- Model files (downloaded by these scripts):
  - `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` (text encoder, Qwen3-VL 32B INT8)
  - `minimax_h3_fl2va_pruned_int8_convrot.safetensors` (FL2VA T2V/I2V diffusion)
  - `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (REF2VA reference video)
  - `minimax_h3_video_vae_fp16.safetensors` (video VAE)
  - `minimax_h3_audio_vae_fp32.safetensors` (audio VAE)
  - `minimax_h3_turbo_4step_ckpt500_comfyui_pruned.safetensors` (turbo LoRA, 4-step)

**Pin constraints baked into the installers (do not relax without testing):**

- PyTorch 2.8.0 + CUDA 12.8 (cu128) for the RunPod path
- `transformers==4.50.3` (pinned for custom-node compatibility)
- `tokenizers>=0.21,<0.22`
- `huggingface-hub>=0.34,<1.0`
- `hf-xet>=1.1,<2.0`
- `Pillow>=11.0.0`
- `numpy==1.26.4`
- ComfyUI custom node: `ComfyUI-Spectrum-MiniMax-H3` from `xmarre/ComfyUI-Spectrum-MiniMax-H3`

**Operator's manual step before first use:** the `Aitrepreneur/FLX` HuggingFace
repo is gated. Set `HF_TOKEN` in your environment before running the scripts, or
the model downloads will fail with a 403.

**Why Mavis ships these as artifacts (not just doc links):** per the operator's
"second home for agents" framing, every tool the pipeline needs should be
self-explanatory to a fresh local model (Spark, Knuckles) picking up the work
next session. Embedding the installers in the repo means a future agent can
reproduce the full ComfyUI H3 host without needing the operator's local SEAP
folder or external network access to the Aitrepreneur YouTube page.
