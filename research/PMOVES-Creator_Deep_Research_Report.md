# PMOVES-Creator Deep Research Report

**Repository**: https://github.com/POWERFULMOVES/PMOVES-Creator.git
**Branch**: PMOVES.AI-Edition-Hardened
**Upstream**: ComfyUI v0.3.68 (comfyanonymous/ComfyUI fork)
**Files Analyzed**: 685+ | **Report Date**: 2026-04-17

---

## 1. PURPOSE & FUNCTION

PMOVES-Creator is a hardened, PMOVES-branded fork of ComfyUI serving as the creative render pipeline for the PMOVES.AI platform. It is a node/graph-based visual AI engine for designing and executing diffusion model workflows.

**Core Role in PMOVES.AI**: Content creation tier (media tier) that generates images, videos, audio, and 3D assets. Outputs feed into n8n automation workflows (Geometry Bus / CGP) for downstream processing, storage (MinIO), and metadata (Supabase).

**Three Primary Workflow Families** (from `pmoves/creator/`):

| Workflow | Purpose | n8n Flow | Output | Key Models |
|----------|---------|----------|--------|------------|
| WAN Animate 2.2 | Text/image-to-video generation | `wan_to_cgp` | MP4 video files | Wan2.2-Animate-14B (FP8) |
| Qwen Image Edit+ | AI-powered image editing (recolor, inpaint) | `qwen_to_cgp` | PNG images | Qwen2.5-VL-7B-Instruct (GGUF), Qwen-Image-Edit-Lightning |
| VibeVoice / RVC | TTS + voice cloning | `vibevoice_to_cgp` | WAV audio | RVC models, VibeVoice TTS |

**Operational Modes**:
- **Standalone**: Runs independently via `docker compose up -d`
- **Hybrid**: Connects to PMOVES.AI services (TensorZero LLM gateway, MinIO storage, Render webhook, NATS message bus)
- **Portable**: Windows/RunPod installer bundles for render workstations

---

## 2. MODEL REQUIREMENTS

### 2.1 Locally-Hosted Diffusion Models (57 Architecture Classes)

**Image Generation**:
| Model Family | Variants | Est. Parameters |
|-------------|----------|----------------|
| SD 1.5 / SD 2.x | SD15, SD20, SD21UnclipL, SD21UnclipH, SD15_instructpix2pix | ~860M-1.5B |
| SDXL | SDXL, SDXLRefiner, SSD1B, Segmind_Vega, KOALA_700M, KOALA_1B, SDXL_instructpix2pix | ~3.5B-6.6B |
| SD3 / SD3.5 | SD3 | ~2B-8B |
| Flux | Flux, FluxInpaint, FluxSchnell | ~12B |
| PixArt | PixArtAlpha, PixArtSigma | ~600M-1.1B |
| AuraFlow | AuraFlow | ~675M |
| HunyuanDiT | HunyuanDiT, HunyuanDiT1 | ~700M-2B |
| HiDream | HiDream | ~1.8B |
| Lumina2 | Lumina2 | ~2B-3B |
| Qwen Image | QwenImage | ~2B-7B |
| Hunyuan Image 2.1 | HunyuanImage21, HunyuanImage21Refiner | ~1B-2B |
| OmniGen 2 | Omnigen2 | ~4B |
| Chroma / ChromaRadiance | Chroma, ChromaRadiance | ~1-2B |
| LotusD | LotusD | ~860M |
| Stable Cascade | Stable_Cascade_C, Stable_Cascade_B | ~1.5B total |

**Video Generation**:
| Model Family | Variants | Est. Parameters |
|-------------|----------|----------------|
| SVD / SV3D | SVD_img2vid, SV3D_u, SV3D_p | ~500M-1.5B |
| Mochi | GenmoMochi | ~10B |
| LTX-Video | LTXV | ~2B |
| Hunyuan Video | HunyuanVideo, HunyuanVideoI2V, HunyuanVideoSkyreelsI2V | ~13B |
| Cosmos | CosmosT2V, CosmosI2V, CosmosT2IPredict2, CosmosI2VPredict2 | ~5-8B |
| Wan 2.1/2.2 | WAN21_T2V, WAN21_I2V, WAN21_FunControl2V, WAN21_Camera, WAN22_Camera, WAN21_Vace, WAN21_HuMo, WAN22_S2V, WAN22_Animate, WAN22_T2V | **14B** (primary: Wan2.2-Animate-14B FP8) |
| HiDream E1.1 | (via Flux Kontext) | ~1.8B |

**Audio Generation**:
| Model Family | Est. Parameters |
|-------------|----------------|
| Stable Audio | ~1.5B |
| ACE Step | ~1.5B |

**3D Generation**:
| Model Family | Est. Parameters |
|-------------|----------------|
| Hunyuan3D 2.0/2.1 | Hunyuan3Dv2, Hunyuan3Dv2_1, Hunyuan3Dv2mini | ~2-4B |

**Upscaling / Enhancement**:
| Model | Type |
|-------|------|
| ESRGAN variants, SwinIR, Swin2SR | Diffusion-based upscale |
| 4x-ClearRealityV1, RealESRGAN_x4plus_anime_6B | Used in Qwen Edit+ workflow |

### 2.2 Text Encoders Referenced
- CLIP (ViT-L/14, ViT-B/32) — SD1.x/SDXL
- CLIP Vision (ViT-L, ViT-H, ViT-G, SigLIP 384/512) — Image conditioning
- OpenCLIP ViT-bigG — SDXL
- T5-XXL (UMT5) — PixArt, Flux, Wan (umt5-xxl-enc-bf16.safetensors)
- T5-XL — Aura, SA-T5
- SD3-CLIP (CLIP-L + OpenCLIP-G + T5-XXL) — SD3
- HunyuanDiT-CLIP — Hunyuan models
- Qwen2.5-VL-7B-Instruct — Qwen Image Edit+ (GGUF quantized)
- LLaMA tokenizer — Video models
- ByT5 — Glyph/character-level encoding
- ACE lyrics tokenizer — Audio models
- BERT — Masked language modeling tasks

### 2.3 Audio Encoders
- Whisper (via `comfy/audio_encoders/whisper.py`) — Speech transcription
- Wav2Vec2 (via `comfy/audio_encoders/wav2vec2.py`) — Audio feature extraction

### 2.4 External API Models (Comfy API Nodes)

| Provider | Models/Endpoints | Modality |
|----------|-----------------|----------|
| Google Veo | Veo 2/3 (text-to-video) | Video |
| Google Gemini | Gemini multimodal (text, image gen, audio) | Multimodal LLM |
| OpenAI | ChatGPT-4o-latest, GPT-4o | Text/Vision LLM |
| BFL (Black Forest Labs) | Flux-Pro-1.0-Expand, Flux-Pro-1.0-Fill, Flux-Pro-1.1-Ultra, Flux-Kontext-Max/Pro | Image/Video |
| Runway | Gen-3a-Turbo, Gen-4-Turbo | Video |
| Kling AI | Kling v1/v1.5/v1.6/v2/v2.6/v3/v3-omni, Kling-image-o1, Kling-video-o1 | Image/Video/3D |
| Luma AI | Luma Video/Image models | Image/Video |
| Pika | Pika video generation | Video |
| Minimax | Minimax video/image | Image/Video |
| ByteDance | Seedream 3.0/4.0/4.5, Seedance 1.0/1.5 | Image/Video |
| PixVerse | PixVerse video generation | Video |
| Stability AI | SD3, Stable Image Ultra, Stable Audio 2 (T2A, A2A), Upscale | Image/Audio |
| Ideogram | Ideogram image generation | Image |
| Recraft | Recraft image generation | Image |
| Tripo AI | Tripo 3D model generation | 3D |
| Rodin AI | Rodin 3D model generation (face count up to 500K) | 3D |
| Moonvalley | Moonvalley video | Video |
| Vidu | Vidu video | Video |
| Sora | OpenAI Sora video generation | Video |
| Meshy AI | Meshy 3D model generation | 3D |

### 2.5 LLM Models (via TensorZero Integration)
- **Default**: Qwen2.5-14B (`TENSORZERO_CHAT_MODEL=qwen2_5_14b`)
- **Embedding**: text-embedding-3-small (`TENSORZERO_EMBED_MODEL`)
- Access via TensorZero Gateway (not direct inference)

---

## 3. GPU REQUIREMENTS

### 3.1 VRAM Tiers (from `comfy/model_management.py`)

| Mode | Flag | Min VRAM | Behavior |
|------|------|----------|----------|
| DISABLED | — | 0 | No GPU, CPU only |
| NO_VRAM | `--novram` | <1 GB | Extreme offloading, model split into minimal chunks |
| LOW_VRAM | `--lowvram` | 2-4 GB | UNet split into parts, aggressive offloading |
| NORMAL_VRAM | `--normalvram` | 6-8 GB | Models unloaded to CPU after use (default) |
| HIGH_VRAM | `--highvram` | 12-16 GB | Models kept in GPU memory |
| GPU_ONLY | `--gpu-only` | 24+ GB | Everything (CLIP, VAE, UNet) on GPU |
| SHARED | (auto) | Variable | Shared CPU/GPU memory (Apple Silicon, iGPU) |

### 3.2 Per-Workflow Practical Requirements

| Workflow | Min VRAM | Recommended | Notes |
|----------|----------|-------------|-------|
| WAN Animate 2.2 (14B FP8) | 12 GB | 24 GB (RTX 4090/5090) | FP8 reduces ~28B FP16 to ~14B; lowvram mode splits model |
| Qwen Image Edit+ (7B GGUF Q4) | 6 GB | 12 GB | GGUF quantized; Lightning LoRA for speed |
| VibeVoice / RVC | 4 GB | 8 GB | Audio models are smaller |
| SDXL Image Gen | 6 GB | 12 GB | Standard SDXL pipeline |
| Flux (12B) | 16 GB | 24 GB | Largest image model natively supported |
| Hunyuan Video (13B) | 16 GB | 24 GB | Video context windows increase memory |
| SD 1.5 / SD 2.x | 4 GB | 8 GB | Legacy models, low requirement |

### 3.3 Multi-GPU Support
- **Docker**: `GPU_COUNT=all` or specific device IDs (`NVIDIA_VISIBLE_DEVICES=0,1`)
- **CLI**: `--cuda-device N` (single GPU mode) or `--default-device N` (multi-GPU)
- **Smart offloading**: Automatically splits models across GPU/CPU when VRAM is insufficient
- **CUDA architecture list**: 5.0 through 9.0 (Maxwell through Blackwell)

### 3.4 CPU-Only Mode
- Supported via `--cpu` flag (explicitly slow per docs)
- AMD ROCm (Linux), Intel XPU (Arc GPUs via IPEX), Apple Silicon (MPS), Huawei Ascend NPU, Cambricon MLU all supported
- DirectML (Windows) supported but deprecated

---

## 4. INFERENCE BACKEND

**Primary: Native PyTorch** (torch >= 2.6.0, pinned to 2.5.1 in Dockerfile with CUDA 12.4)

- No vLLM, llama.cpp, Ollama, TensorRT-LLM, or TGI for LLM inference
- LLM access via TensorZero Gateway (external service, not local inference)
- Diffusion models run directly through ComfyUI's custom execution engine (`comfy_execution/`)
- Custom k-diffusion samplers (DEIS, SA-Solver, uni_pc)
- `torch._scaled_mm` for FP8 matmul (hardware-accelerated Tensor Core path)
- Optional: SageAttention + Triton acceleration (via installer scripts)

**Execution Engine** (`comfy_execution/graph.py`):
- Asynchronous node execution with dependency resolution
- Intelligent caching: only re-executes changed parts of the workflow graph
- LRU node caching option (`--cache-lru N`)
- Progress isolation per execution

---

## 5. QUANTIZATION SUPPORT

### 5.1 Native FP8 (Built-in)
- **Format**: `torch.float8_e4m3fn` (primary), `torch.float8_e5m2`
- **Implementation**: `comfy/quant_ops.py` — `TensorCoreFP8Layout` class with `torch._scaled_mm` hardware acceleration
- **Activation**: Automatic on FP8-capable GPUs (Ada Lovelace+); can force with `--supports-fp8-compute`
- **Scope**: Linear layers (aten.linear, aten.addmm, aten.mm) — weight and activation quantization
- **Fallback**: Automatic dequantization for unsupported operations
- **Supported FP8 types detected**: e4m3fn, e4m3fnuz, e5m2, e5m2fnuz, e8m0fnu

### 5.2 FP16/FP32
- `--force-fp16` / `--force-fp32` (global precision)
- `--fp16-unet` / `--fp32-unet` (diffusion model precision)
- `--fp16-vae` / `--fp32-vae` (VAE precision)
- `--fp16-text-enc` / `--fp32-text-enc` (text encoder storage)
- `--fp16_accumulation` (performance feature flag)
- `--cpu-vae` (run VAE on CPU to save GPU VRAM)

### 5.3 GGUF (via Custom Node)
- ComfyUI-GGUF custom node referenced in installer scripts
- Used for Qwen2.5-VL-7B-Instruct GGUF quantized variants in Qwen Image Edit+ workflow
- Not built-in; requires external custom node installation

### 5.4 Pluggable Quantization Architecture
- `QuantizedLayout` base class allows adding new formats (INT4, INT8, AWQ, GPTQ)
- `QuantizedTensor` torch.Tensor subclass with `__torch_dispatch__` for transparent operation handling
- Currently only `TensorCoreFP8Layout` is registered in `LAYOUTS` dict
- Bitsandbytes not referenced in requirements or source

---

## 6. CONTEXT WINDOW NEEDS

### 6.1 Text Encoder Context
| Encoder | Typical Context | Notes |
|---------|----------------|-------|
| CLIP (SD1.x) | 75 tokens | Fixed position embedding |
| CLIP (SDXL) | 77 tokens | Dual-encoder (CLIP-L + OpenCLIP-G) |
| T5-XXL | 512 tokens | Used by Flux, PixArt, Wan |
| SD3-CLIP | 77+256 tokens | Triple encoder |
| HunyuanDiT-CLIP | Variable | Chinese/English bilingual |
| Qwen2.5-VL | 32K+ tokens | VL model, image tokens expand context |

### 6.2 Video Frame Context Windows
- **Mechanism**: `comfy/context_windows.py` — `IndexListContextHandler` with configurable frame windows
- **Schedules**: `uniform_looped`, `uniform_standard`, `static_standard`, `batched`
- **Fuse Methods**: `flat`, `pyramid`, `relative`, `overlap-linear`
- **Parameters**: `context_length` (frames per window), `context_overlap`, `context_stride`
- **Typical**: Video models process 16-100 frames per window with overlap for temporal coherence
- **Classification**: MEDIUM (4K-32K tokens) for text; VARIABLE for video (frame count, not token count)

### 6.3 Overall Assessment
- **Image workflows**: SHORT (<4K tokens)
- **Video workflows**: MEDIUM to LONG (depends on frame count and resolution; 100 frames at 512 tokens = 50K+ effective context)
- **VL editing (Qwen)**: LONG (32K+ tokens with image patches)

---

## 7. THROUGHPUT REQUIREMENTS

### 7.1 Operational Profile
- **Primary**: BATCH processing with interactive preview
- **Queue System**: Asynchronous queue with priority support (`Ctrl+Shift+Enter` for first-in-queue)
- **Worker Config** (env.tier-worker.sh): `MAX_CONCURRENT_JOBS=10`, `WORKER_POOL_SIZE=4`, `JOB_TIMEOUT_MS=600000` (10 min)
- **Media timeout**: 30 minutes (`MEDIA_TIMEOUT_MS=1800000`)
- **Progress reporting**: Every 5 seconds (`PROGRESS_REPORT_INTERVAL_MS=5000`)

### 7.2 Latency Expectations
- **SDXL image**: ~2-10 seconds on RTX 4090 (depends on steps, resolution)
- **Flux 12B**: ~10-30 seconds per image
- **Wan 2.2 14B video (FP8)**: ~1-5 minutes per clip (depends on frame count, resolution, steps)
- **Qwen Image Edit+**: ~5-15 seconds per edit (GGUF + Lightning LoRA for speed)
- **Not real-time interactive**: Generation is queued, not streaming (except latent previews)

### 7.3 Preview System
- **Fast preview**: Default low-resolution latent preview
- **High-quality preview**: TAESD decoder (requires downloaded decoder models)
- **Preview methods**: `auto`, `taesd`, `latent2rgb`

---

## 8. DGX SPARK ACCELERATION POTENTIAL

### 8.1 Direct Acceleration Opportunities

| Feature | DGX Spark Benefit | Impact |
|---------|-------------------|--------|
| **FP8 `torch._scaled_mm`** | Native FP8 Tensor Core on Hopper (H100/H200) — 2x throughput over FP16 | HIGH — all diffusion models benefit |
| **Multi-GPU model parallelism** | NVLink 900 GB/s allows splitting large models (Wan 14B, Flux 12B, Hunyuan 13B) across GPUs without PCIe bottleneck | HIGH — eliminates lowvram/novram mode entirely |
| **Video batch processing** | 128GB HBM3e per GPU enables batching multiple video frames/windows concurrently | HIGH — parallel context window execution |
| **HBM3e capacity** | 128GB per GPU means even 14B FP16 models fit entirely in VRAM without offloading | HIGH — eliminates CPU↔GPU transfer overhead |
| **CUDA 12.4 + PyTorch 2.6** | Already compatible; DGX Spark drivers support CUDA 12.x | MEDIUM — no code changes needed |

### 8.2 Recommended DGX Spark Configuration

```
# For single-GPU (one H100 80GB):
python main.py --highvram --force-fp16 --listen 0.0.0.0

# For multi-GPU (DGX Spark with 8x H100 128GB):
python main.py --gpu-only --default-device 0
# (Future: native tensor parallelism would be even better)

# For maximum throughput video pipeline:
python main.py --gpu-only --preview-method auto --cache-lru 10
```

### 8.3 Architecture Enhancements for DGX Spark

1. **Tensor Parallelism**: ComfyUI currently uses single-GPU inference. Adding tensor parallel (e.g., via PyTorch DTensor or custom model splitting) would allow Wan 14B / Hunyuan 13B to run on 2-4 GPUs simultaneously, halving latency.

2. **Pipeline Parallelism**: The graph execution engine could be modified to run independent nodes on separate GPUs — e.g., text encoder on GPU 0, UNet on GPU 1, VAE on GPU 2.

3. **Concurrent Workflow Execution**: DGX Spark's 8 GPUs could run 4-8 independent image generation workflows in parallel (each on its own GPU), multiplying throughput for batch jobs.

4. **FP8-Optimized Video**: The `TensorCoreFP8Layout` class directly maps to Hopper FP8 Tensor Cores. No changes needed — it already uses `torch._scaled_mm` which is the Hopper-optimized path.

5. **Larger Context Windows**: 128GB HBM3e enables processing longer video sequences in a single context window (currently limited by VRAM), improving temporal coherence.

### 8.4 Integration with PMOVES.AI
- **Service name**: `content-creator` (from env.shared)
- **Tier**: `media` (from docker-compose.pmoves.yml) — `GPU_ENABLED=true`, `MAX_CONCURRENT_JOBS=4`
- **GPU Orchestrator**: Defined in env.shared (`GPU_ORCHESTRATOR_URL=http://gpu-orchestrator:8050`) — suggests future multi-GPU scheduling
- **NATS**: Job queue via JetStream for distributing render jobs across GPU workers
- **TensorZero**: LLM calls routed through gateway, not local — no GPU contention for LLM inference

---

## 9. KEY DEPENDENCIES

### 9.1 Core Dependencies (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| torch | >=2.6.0 | Core inference engine (Dockerfile pins 2.5.1) |
| torchvision | — | Image transforms, pre-trained models |
| torchaudio | — | Audio processing |
| torchsde | — | SDE samplers for diffusion |
| transformers | >=4.37.2 | HuggingFace model loading (CLIP, T5, BERT, etc.) |
| tokenizers | >=0.13.3 | Text tokenization |
| sentencepiece | — | T5/ByT5 tokenization |
| safetensors | >=0.4.2 | Safe model serialization |
| numpy | >=1.25.0 | Numerical computing |
| einops | — | Tensor rearrangement (attention, video) |
| aiohttp | >=3.11.8 | Async HTTP (API nodes, webhooks) |
| yarl | >=1.18.0 | URL parsing (aiohttp dependency) |
| Pillow | — | Image I/O and processing |
| scipy | — | Signal processing, interpolation |
| tqdm | — | Progress bars |
| psutil | — | System/memory monitoring |
| av | >=14.2.0 | PyAV — video read/write (FFmpeg bindings) |
| alembic | — | Database migrations |
| SQLAlchemy | — | ORM for user/settings database |

### 9.2 Optional Dependencies

| Package | Purpose |
|---------|---------|
| kornia | >=0.7.1 — Computer vision (Canny edge detection node) |
| spandrel | Image super-resolution model loading |
| pydantic | ~=2.0 — API node data validation |
| pydantic-settings | ~=2.0 — Configuration management |

### 9.3 Frontend

| Package | Version | Purpose |
|---------|---------|---------|
| comfyui-frontend-package | 1.28.8 | Bundled Vue/TS frontend |
| comfyui-workflow-templates | 0.2.11 | Built-in workflow templates |
| comfyui-embedded-docs | 0.3.1 | In-app documentation |

### 9.4 PMOVES-Specific (not in requirements.txt)

| Component | Purpose |
|-----------|---------|
| pmoves_announcer | Service discovery/announcement module |
| pmoves_common | Shared PMOVES utilities |
| pmoves_health | Health check endpoints |
| pmoves_registry | Service registry integration |
| middleware/cache_middleware | Response caching |
| chit/secrets_manifest_v2.yaml | Secrets management via CHIT Vault |

### 9.5 Custom Nodes Referenced (not bundled)

- ComfyUI-GGUF (GGUF model loading)
- KJNodes (utility nodes)
- WanVideoWrapper (Wan model support)
- ComfyUI-Manager (node package manager)
- SageAttention + Triton (acceleration)
- VibeVoice RVC nodes (voice cloning)

---

## 10. ARCHITECTURE NOTES

### 10.1 Core Architecture

```
main.py → server.py (aiohttp) → comfy_execution/graph.py (node executor)
                                          ↓
                              comfy/model_management.py (VRAM/GPU orchestration)
                                          ↓
                              comfy/model_patcher.py (model loading/offloading)
                                          ↓
                              comfy/supported_models.py (57 model architectures)
                                          ↓
                    ┌─────────────────┼─────────────────┐
               comfy/ldm/*     comfy/text_encoders/*  comfy/k_diffusion/*
               (diffusion       (CLIP, T5, Qwen,      (samplers: DEIS,
                model impls)     Hunyuan, etc.)         SA-Solver, uni_pc)
```

### 10.2 API Layer
- **Primary API**: aiohttp-based REST API on port 8188
- **Endpoints**: `/system_stats`, `/prompt` (queue), `/history`, `/view`, `/upload`
- **WebSocket**: Real-time progress and preview streaming
- **Internal routes**: `api_server/routes/internal/internal_routes.py` — terminal service
- **Comfy API nodes**: Proxy-based external API calls through `/proxy/{provider}/...` endpoints

### 10.3 Database
- **Engine**: SQLAlchemy + Alembic (migrations in `alembic_db/`)
- **Models**: `app/database/models.py` — user management, settings, workflow persistence
- **Config**: `alembic.ini`

### 10.4 Model Loading Architecture
- `comfy/model_detection.py` — Auto-detects model type from state dict keys
- `comfy/model_patcher.py` — Wraps models for lazy loading, precision control, LoRA injection
- `comfy/lora.py` — LoRA/LoCon/LoHA/LoKR/OFT/BoFT/gLoRA weight adapter support
- `comfy/diffusers_load.py` — Convert/load HuggingFace Diffusers format
- `comfy/weight_adapter/` — Modular weight adapter system
- `folder_paths.py` — Centralized model path resolution with `extra_model_paths.yaml` support

### 10.5 Quantization Pipeline
```
QuantizedTensor (torch.Tensor subclass)
    ↓ __torch_dispatch__
    ├─ Generic utils (detach, clone, to) → layout-agnostic
    ├─ Layout-specific ops (linear, mm) → TensorCoreFP8Layout → torch._scaled_mm
    └─ Fallback → dequantize to original dtype → standard PyTorch op
```

### 10.6 Context Window Pipeline (Video)
```
IndexListContextHandler
    ├─ should_use_context() → check if frames > context_length
    ├─ get_context_windows() → apply schedule (uniform_looped, static, batched)
    ├─ evaluate_context_windows() → execute per-window inference
    └─ combine_context_window_results() → fuse with weights (pyramid, relative, overlap-linear)
```

### 10.7 Docker Architecture
- **Multi-stage build**: builder (Python + PyTorch + deps) → runtime (minimal OS + venv copy)
- **Base image**: `nvidia/cuda:12.4.0-cudnn9-runtime`
- **Health check**: `curl -f http://localhost:8188/system_stats` (30s interval)
- **Volumes**: `comfyui-models`, `comfyui-output`, `comfyui-data` (HF cache)
- **Network**: `pmoves_pmoves_app` (external bridge network for service mesh)
- **Optional nginx**: Production reverse proxy (separate profile)

### 10.8 PMOVES Integration Points

| Integration | Mechanism | Status |
|------------|-----------|--------|
| TensorZero LLM Gateway | HTTP API (`TENSORZERO_URL`) | Configured, default qwen2_5_14b |
| MinIO Object Storage | S3-compatible (`MINIO_ENDPOINT`) | Configured, bucket `pmoves-comfyui` |
| Render Webhook | HTTP POST (`RENDER_WEBHOOK_URL`) | Configured, output handling |
| NATS Message Bus | JetStream (`NATS_URL`) | Configured in env.shared |
| Supabase | REST API | Referenced in workflows (metadata) |
| GPU Orchestrator | HTTP API (`GPU_ORCHESTRATOR_URL`) | Defined, not yet wired |
| CHIT Vault | Secrets management | Manifest template created |
| Prometheus | Metrics endpoint | Labels configured in pmoves anchors |

### 10.9 Notable Design Patterns

1. **Lazy model evaluation**: Models loaded on first use, offloaded after execution (unless highvram mode)
2. **Graph caching**: Only changed subgraphs re-execute between runs
3. **Pluggable quantization**: `QuantizedLayout` base class enables adding new formats without modifying core
4. **Weight adapter chain**: Multiple adapters (LoRA, LoHA, LoKR, etc.) can be stacked on a single model
5. **Context window abstraction**: Video models use a unified context window system regardless of model architecture
6. **API node proxy pattern**: External API calls are abstracted as ComfyUI nodes with async polling
7. **Tier-based environment**: YAML anchors in `docker-compose.pmoves.yml` provide reusable env configs per tier

---

## Summary Assessment

PMOVES-Creator is a production-grade creative rendering engine with exceptional model coverage (57 architectures + 20 external APIs), sophisticated memory management (5 VRAM tiers with smart offloading), and native FP8 Tensor Core support. Its primary value to PMOVES.AI is as the media generation tier producing images, videos, and audio for downstream n8n automation pipelines.

**DGX Spark Fit**: EXCELLENT. The 128GB HBM3e per GPU eliminates all offloading for any current model (including 14B video models in FP16). NVLink enables future tensor parallelism for sub-linear latency scaling. FP8 `torch._scaled_mm` is already the native code path. The main gap is that ComfyUI lacks built-in multi-GPU model parallelism — this would need to be added (via DTensor or custom sharding) to fully exploit DGX Spark's NVLink bandwidth for single-workflow acceleration. However, multi-GPU concurrent workflow execution works out of the box.

**Integration Maturity**: EARLY. The PMOVES.AI_INTEGRATION.md is mostly TBD. Docker and env configuration is solid, but NATS subjects, MCP endpoints, auth/JWT, and boot order are undefined. The submodule was empty (uninitialized) at time of audit — the actual PMOVES overlay has not been applied yet.
