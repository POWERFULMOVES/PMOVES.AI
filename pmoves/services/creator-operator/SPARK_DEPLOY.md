# OmniVoice-on-SPARK (DGX Spark) — Deploy & Validation Plan

**Node:** `spark` — NVIDIA DGX Spark, **GB10 Grace-Blackwell, ARM64 + CUDA**, 128GB unified memory.
**Reach:** `pmoves-spark` (Tailscale hostname — never a raw 100.x IP).
**Operator-node caps:** `[cuda, comfyui, browser, voice]`  (see `pmoves/config/operator_nodes.yaml`).
**Status:** TODO-validate seam — **do NOT route live voice to SPARK until every step below passes.**

> ⚠️ **This is a scaffold, NOT a verified deployment.** It was authored on a machine
> with **no SPARK / arm64 / GPU**. The image has **not** been built and the server has
> **not** been run or GPU-tested here. Every node-specific instruction is marked
> **TODO-confirm-on-node**. Treat all version/wheel/tag values as placeholders to verify.

---

## Background

OmniVoice (Apache-2.0, `k2-fsa/OmniVoice`) was live-validated on NVIDIA x86 (4090, Torch
2.8.0+cu128, 2026-06-10) and has a ROCm validation seam for `knuckles` (see
`ROCM_VALIDATION.md`). SPARK is the third deploy target: it carries the `voice` cap, but
unlike the x86 NVIDIA nodes it is **arm64**, so the stock cu128 torch wheel (an x86_64
build) will **not** install. SPARK needs the **arm64/sbsa CUDA** torch wheel.

This document captures the deploy unit (Dockerfile + compose service + make targets) and
what must be swapped/verified before flipping routing to SPARK.

This is the deploy-unit analog of the manual workflow:

```bash
# OLD (manual, not fleet-managed):
OMNIVOICE_TOKEN=... OMNIVOICE_DEVICE=cuda:0 python omnivoice_server.py
```

---

## 1. arm64/sbsa CUDA Torch/Torchaudio Wheel Swap  (TODO-confirm-on-node)

The `nvidia-smi` analog here is the **same** `nvidia-smi` (SPARK is CUDA, not ROCm — there
is no `rocm-smi`). On x86 NVIDIA nodes the default install is:

```
torch torchaudio --index-url https://download.pytorch.org/whl/cu128
```

On SPARK (arm64) that x86_64 cu128 wheel does not apply. The **exact arm64/sbsa CUDA
wheel tag and index URL is TODO-confirm-on-node** — do NOT hardcode a guess. On the node:

```bash
# 1) Ground-truth the CUDA stack and arch:
nvidia-smi                       # confirm GPU + driver + CUDA version (expect 12.8+)
uname -m                         # expect: aarch64
# 2) Select the matching arm64/sbsa PyTorch index from the official matrix at
#    https://pytorch.org/get-started/locally/ (Linux / aarch64 / CUDA 12.8+).
#    NVIDIA also publishes Grace-Blackwell (sbsa) torch builds via the NGC /
#    PyPI sbsa channels — verify which currently serves a Blackwell-compatible wheel.
```

The Dockerfile install command is **ARG-driven** so no guess is baked in. Override at
build time (values below are PLACEHOLDERS — TODO-confirm-on-node):

```bash
docker compose -f services/creator-operator/docker-compose.omnivoice.yml --profile voice build \
  --build-arg OMNIVOICE_TORCH_INDEX_URL=<arm64-sbsa-cu12x-index>   # TODO-confirm-on-node
# (or set OMNIVOICE_TORCH_INDEX_URL / OMNIVOICE_TORCH_SPEC in the node env file)
```

Everything else in `requirements-prod.txt` (`omnivoice`, `soundfile`, `fastapi`,
`uvicorn`, `prometheus_client`) installs identically on arm64 — no changes needed there.

### 1a. Verify the swap is clean (TODO-confirm-on-node)

After build, confirm torch sees the GPU inside the container:

```bash
docker run --rm --gpus all $${OMNIVOICE_IMAGE:-pmoves-omnivoice:latest} \
  python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Expected: a +cu12x version string, True, and the GB10 / Blackwell device name.
```

---

## 2. CUDA Device String  (no code change)

`OMNIVOICE_DEVICE=cuda:0` (the `omnivoice_server.py` default) is correct on SPARK —
SPARK is native CUDA, so `cuda:0` is literal (no HIP remap as on ROCm). No edits to
`omnivoice_server.py` are needed. With 128GB unified memory, a single device is the
default; pin `OMNIVOICE_DEVICE=cuda:1` only if the node enumerates multiple CUDA devices.

The server binds `OMNIVOICE_HOST=0.0.0.0` / `OMNIVOICE_PORT=8002` inside the container
(set in the Dockerfile + compose env) so it is reachable in-compose and over the mesh.
The `__main__` guard in `omnivoice_server.py` honors both env vars.

---

## 3. Deploy Unit

Three companion files make up the deploy unit:

| File | Role | Protected? |
|------|------|-----------|
| `Dockerfile.omnivoice` | multiarch image (amd64+arm64), ARG-driven torch index | no |
| `docker-compose.omnivoice.yml` | `omnivoice-server` service (GPU reservation, healthcheck, HF cache) | **yes — compose Known Road** |
| `pmoves/Makefile` | `omnivoice-build` / `omnivoice-up` / `omnivoice-down` | no |

### 3a. Operator: install the compose file (compose Known Road)

`docker-compose*.yml` paths are damage-control-protected (the `compose` Known Road class,
matched by basename — even service-local). The PR author could not write it in-session, so
**the operator creates it** from the snippet below.

Save exactly as `pmoves/services/creator-operator/docker-compose.omnivoice.yml`, opening the
guard with a provable reason in the shell that launches the editor/agent:

```bash
export KNOWN_ROAD=compose:pr:<this-PR-number>   # or compose:handoff:<brief>.md
```

<details>
<summary><code>docker-compose.omnivoice.yml</code> (paste-ready)</summary>

```yaml
# docker-compose.omnivoice.yml — OmniVoice production voice server deploy unit.
# Opt-in via the `creator` or `voice` profiles. Build context = THIS directory
# (omnivoice_server.py does not import services.common). GPU via the NVIDIA
# container runtime (deploy.resources reservation), not baked into the image.
#   docker compose -f services/creator-operator/docker-compose.omnivoice.yml \
#     --profile voice up -d omnivoice-server
# SPARK (arm64+CUDA GB10): set OMNIVOICE_PLATFORM=linux/arm64.
services:
  omnivoice-server:
    build:
      context: .
      dockerfile: Dockerfile.omnivoice
      args:
        CUDA_BASE_TAG: ${OMNIVOICE_CUDA_BASE_TAG:-12.8.1-runtime-ubuntu22.04}
        TORCH_INDEX_URL: ${OMNIVOICE_TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}
        TORCH_SPEC: ${OMNIVOICE_TORCH_SPEC:-torch torchaudio}
    image: ${OMNIVOICE_IMAGE:-pmoves-omnivoice:latest}
    platform: ${OMNIVOICE_PLATFORM:-}   # SPARK: linux/arm64
    restart: unless-stopped
    ports:
      - "${OMNIVOICE_BIND:-127.0.0.1}:${OMNIVOICE_HOST_PORT:-8002}:8002"
    environment:
      - OMNIVOICE_HOST=0.0.0.0
      - OMNIVOICE_PORT=8002
      - OMNIVOICE_DEVICE=${OMNIVOICE_DEVICE:-cuda:0}
      - OMNIVOICE_TOKEN=${OMNIVOICE_TOKEN:-}
      - OMNIVOICE_MODEL=${OMNIVOICE_MODEL:-k2-fsa/OmniVoice}
      - OMNIVOICE_LOAD_ASR=${OMNIVOICE_LOAD_ASR:-0}
      - OMNIVOICE_REFERENCE_VOICE_DIR=${OMNIVOICE_REFERENCE_VOICE_DIR:-}
      - HF_HOME=/cache/huggingface
    volumes:
      - omnivoice-hf-cache:/cache/huggingface
      # Optional ref-voice catalog (clone mode), read-only host bind:
      # - ${OMNIVOICE_REFERENCE_VOICE_HOST_DIR:-./voices}:/voices:ro
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8002/healthz"]
      interval: 30s
      timeout: 5s
      start_period: 120s
      retries: 5
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
              count: ${OMNIVOICE_GPU_COUNT:-all}
    profiles: ["creator", "voice"]
volumes:
  omnivoice-hf-cache: {}
```

</details>

### 3b. Build + run via make (SPARK)

```bash
# Set the node env first (TODO-confirm-on-node for the torch index):
export OMNIVOICE_PLATFORM=linux/arm64
export OMNIVOICE_TORCH_INDEX_URL=<arm64-sbsa-cu12x-index>   # TODO-confirm-on-node
export OMNIVOICE_TOKEN=<test-token>
export OMNIVOICE_BIND=127.0.0.1        # or the tailnet bind to mesh-expose

make -C pmoves omnivoice-build         # buildx/compose build
make -C pmoves omnivoice-up            # compose up -d (voice profile)
# ... validate (section 4) ...
make -C pmoves omnivoice-down          # stop (keeps omnivoice-hf-cache volume)
```

First run downloads `k2-fsa/OmniVoice` (~several GB) into the `omnivoice-hf-cache` named
volume; subsequent restarts reuse it (`HF_HOME=/cache/huggingface`).

### 3c. Operator: fleet-compose integration (optional)

To fold OmniVoice into the **root** fleet stack (so it starts with the standard overlays /
arm64 override) rather than the service-local file, the operator adds — under the compose
Known Road — both of these (TODO-operator):

1. A `pmoves/docker-compose.creator.yml` with the same `omnivoice-server` service but
   `build.context: ./services/creator-operator` and `dockerfile: Dockerfile.omnivoice`.
2. An entry in `pmoves/docker-compose.arm64.override.yml` (the SPARK arm64 hook):

   ```yaml
   services:
     omnivoice-server:
       platform: linux/arm64
   ```

Both root paths require `KNOWN_ROAD=compose:<reason>` (see `.claude/PATTERNS.md` § Known
Roads — Protected-File Edits). The service-local file in 3a is the minimum needed to run.

---

## 4. Smoke Acceptance Steps  (run on SPARK after build)

Use the existing harness `scripts/rocm_smoke.sh` — it is **node-agnostic** (despite the
name) and validates `/healthz` → token-gated `/synthesize` → 24 kHz mono WAV in one shot.
Point it at the deployed `:8002`:

```bash
bash scripts/rocm_smoke.sh http://127.0.0.1:8002 "$OMNIVOICE_TOKEN" /tmp/spark_smoke.wav
# Expected tail:  PASS: <N> bytes, 24000 Hz mono, <duration>s — OmniVoice ... smoke OK
```

### 4a. /healthz (TODO-confirm-on-node)

```bash
curl -s http://127.0.0.1:8002/healthz | python3 -m json.tool
```

Expected shape (note `device: cuda:0` is literal CUDA on SPARK):

```json
{
  "status": "ok",
  "model": "k2-fsa/OmniVoice",
  "device": "cuda:0",
  "asr": false,
  "auth": true,
  "catalog": false,
  "sample_rate": 24000
}
```

`"status": "ok"` confirms the model loaded into VRAM.

### 4b. Token-gated /synthesize (design mode)  (TODO-confirm-on-node)

```bash
curl -s -X POST http://127.0.0.1:8002/synthesize \
  -H "Content-Type: application/json" \
  -H "X-OmniVoice-Token: $OMNIVOICE_TOKEN" \
  -d '{"text": "OmniVoice SPARK smoke test.", "instruct": "female, young adult"}' \
  -o /tmp/spark_smoke.wav
```

A missing/wrong `X-OmniVoice-Token` MUST return `401` when `OMNIVOICE_TOKEN` is set —
verify the gate:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8002/synthesize \
  -H "Content-Type: application/json" -d '{"text":"no token"}'   # expect 401
```

### 4c. Assert 24 kHz mono WAV  (TODO-confirm-on-node)

```bash
python3 - /tmp/spark_smoke.wav <<'EOF'
import wave, sys, os
path = sys.argv[1]
size = os.path.getsize(path)
assert size > 1024, f"file too small: {size} bytes"
with wave.open(path) as w:
    assert w.getframerate() == 24000, f"unexpected sample rate: {w.getframerate()}"
    assert w.getnchannels() == 1, f"unexpected channels: {w.getnchannels()}"
print(f"PASS: {size} bytes, 24 kHz mono, {w.getnframes()/w.getframerate():.2f}s")
EOF
```

---

## 5. Risks and Mitigations

### 5a. arm64 wheel availability for Blackwell (TODO-confirm-on-node)
The single biggest risk: a Blackwell-compatible **arm64/sbsa** torch wheel must exist for
the CUDA version SPARK runs. A mismatch fails `import torch` or GPU init. **Mitigation:**
ground-truth `nvidia-smi` + `uname -m` on-node and pick the index from the official matrix
before building (section 1). Do not assume cu128 x86 applies.

### 5b. flash-attention / bitsandbytes
These are often absent or arch-fragile on arm64. OmniVoice falls back to **SDPA** when
flash-attention is missing — the standard PyTorch fallback. **Mitigation:** do NOT install
flash-attention/bitsandbytes; confirm synthesis completes on the SDPA path.

### 5c. Model download on first run
`k2-fsa/OmniVoice` pulls ~several GB. The `omnivoice-hf-cache` named volume persists it
across restarts (`HF_HOME=/cache/huggingface`). **Mitigation:** ensure adequate disk on
SPARK; the named volume keeps it off ephemeral container layers.

### 5d. Multiarch base image tag
`nvidia/cuda:<tag>-runtime-ubuntu22.04` must publish an arm64 variant for the chosen tag.
**Mitigation:** the `CUDA_BASE_TAG` build ARG lets the operator pin a tag confirmed to
exist for both arches (TODO-confirm-on-node).

---

## 6. Capacity-Routing Note

`operator_nodes.yaml` cap declarations control which workloads route to which nodes.

| Node | caps | Voice routing |
|------|------|---------------|
| `4090` / `5090` / `z890` | `[cuda, comfyui, browser, voice]` | live (x86 NVIDIA, cu128) |
| `spark` | `[cuda, comfyui, browser, voice]` | **gated** — this seam (arm64+CUDA) |
| `knuckles` | `[rocm, voice]` | gated — ROCm seam (`ROCM_VALIDATION.md`) |

**Gate before enabling live routing to SPARK:** all of section 4 (4a `/healthz` ok, 4b
token gate + synth 200, 4c 24 kHz mono WAV) must pass on `spark`. Record the node
hostname, `nvidia-smi` CUDA version, `torch.__version__`, the arm64/sbsa index URL used,
and the PASS output in a comment on the enabling PR.

**Do not route live voice to SPARK until these pass.**

---

## 7. P7 / PBnJ Launch

The `pbnj/` launcher tree (`pbnj/pinokio/api/pmoves-services/SKILL.md`) is **not present in
this repo** — it lives Pinokio-side. When that tree is wired, the OmniVoice control line
belongs under `pbnj/pinokio/api/pmoves-services/` and should drive the same compose profile:

```bash
# P7 / pterm launch (compose-profile invocation the SKILL should wrap):
pterm start -- make -C pmoves omnivoice-up      # voice profile, GPU via nvidia runtime
# health:  curl -s http://127.0.0.1:8002/healthz
# stop:    pterm start -- make -C pmoves omnivoice-down
```

P7 (rooms-on-a-stage) selects a `voice`-capable room and loads this service via the
`voice` compose profile. Until the PBnJ SKILL exists, the `make omnivoice-up/down` targets
(section 3b) are the launch surface.

---

## References

- `pmoves/services/creator-operator/omnivoice_server.py` — `/healthz` + `/synthesize` + `/metrics`
- `pmoves/services/creator-operator/Dockerfile.omnivoice` — multiarch image, ARG torch index
- `pmoves/services/creator-operator/requirements-prod.txt` — prod deps (torch installed per-node)
- `pmoves/services/creator-operator/ROCM_VALIDATION.md` — the knuckles (ROCm) analog
- `pmoves/services/creator-operator/scripts/rocm_smoke.sh` — node-agnostic smoke harness
- `pmoves/config/operator_nodes.yaml` — spark cap declaration
- `pmoves/Makefile` — `omnivoice-build` / `omnivoice-up` / `omnivoice-down`
