# OmniVoice-on-ROCm (Knuckles) — Validation Plan

**Node:** `knuckles` — AMD Ryzen 9 9850X3D + dual Radeon RX 9700 (ROCm).
**Operator-node caps:** `[rocm, voice]`  (see `pmoves/config/operator_nodes.yaml`).
**Status:** TODO-validate seam — do not route live voice to knuckles until all steps below pass.

---

## Background

OmniVoice (Apache-2.0, `k2-fsa/OmniVoice`) was live-validated on NVIDIA (4090, Torch
2.8.0+cu128, 2026-06-10).  Knuckles carries the `voice` cap and can receive
`voice.omnivoice` workloads, but OmniVoice's default installer pins a CUDA (`cu*`) torch
build.  This document captures what must be swapped and verified before flipping routing.

---

## 1. ROCm Torch/Torchaudio Wheel Swap

The CUDA wheel pin in `requirements-prod.txt` (`--index-url
https://download.pytorch.org/whl/cu128`) must be replaced with the ROCm index URL on
knuckles.  The exact ROCm wheel tag to use is **TODO-confirm-on-node** — verify the
installed ROCm stack version on `knuckles` (`rocm-smi --version` or
`/opt/rocm/bin/rocminfo`) and select the matching PyTorch index URL from:

```
https://download.pytorch.org/whl/rocm<VERSION>/
```

Replace the CUDA install command with:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/rocm<VERSION>/
# <VERSION> = TODO-confirm-on-node (e.g. 6.1, 6.2 — do NOT assume)
```

Everything else in `requirements-prod.txt` (`omnivoice`, `soundfile`, `fastapi`,
`uvicorn`) installs identically on ROCm — no changes needed there.

### 1a. Verify the swap is clean

After install, confirm no residual CUDA wheels shadow the ROCm build:

```bash
python -c "import torch; print(torch.__version__, torch.version.hip)"
# Expected: version string + HIP version — NOT None
```

---

## 2. PyTorch-ROCm CUDA Compatibility Shim

PyTorch-ROCm maps the `cuda` device string to HIP at runtime.  This is a documented
PyTorch behaviour, not a workaround:

- `torch.cuda.is_available()` returns `True` on a ROCm-enabled GPU.
- `torch.device("cuda:0")` resolves to the first HIP device.
- `OMNIVOICE_DEVICE=cuda:0` (the `omnivoice_server.py` default) therefore works
  on knuckles **without any server-side code changes**.
- `OmniVoice.from_pretrained(..., device_map="cuda:0", ...)` likewise routes to
  HIP device 0 transparently.

No edits to `omnivoice_server.py` or `OMNIVOICE_DEVICE` are needed for basic
ROCm operation.

---

## 3. Smoke Acceptance Steps

Run these on `knuckles` after completing the wheel swap (section 1).

### 3a. Launch the server

```bash
# In a ROCm venv with requirements-prod.txt installed:
OMNIVOICE_TOKEN=<test-token> \
OMNIVOICE_DEVICE=cuda:0 \
python omnivoice_server.py
# Binds 127.0.0.1:8002 by default.
```

Wait for the model to load (first run downloads `k2-fsa/OmniVoice` from HF;
subsequent runs use the cache).  Watch for `"status": "ok"` in the next step.

### 3b. /healthz check

```bash
curl -s http://127.0.0.1:8002/healthz | python -m json.tool
```

Expected response shape:

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

`"status": "ok"` confirms the model is loaded.  `"device": "cuda:0"` is correct
even on ROCm — that string maps to HIP device 0.

### 3c. Token-gated /synthesize (design mode)

```bash
curl -s -X POST http://127.0.0.1:8002/synthesize \
  -H "Content-Type: application/json" \
  -H "X-OmniVoice-Token: <test-token>" \
  -d '{"text": "OmniVoice ROCm smoke test.", "instruct": "female, young adult"}' \
  -o /tmp/rocm_smoke.wav
```

### 3d. Assert 24 kHz WAV

```bash
python - <<'EOF'
import wave, sys, os
path = "/tmp/rocm_smoke.wav"
size = os.path.getsize(path)
assert size > 1024, f"file too small: {size} bytes"
with wave.open(path) as w:
    assert w.getframerate() == 24000, f"unexpected sample rate: {w.getframerate()}"
    assert w.getnchannels() == 1, f"unexpected channels: {w.getnchannels()}"
print(f"PASS: {size} bytes, 24 kHz mono, {w.getnframes()/w.getframerate():.2f}s")
EOF
```

Expected output: `PASS: <N> bytes, 24 kHz mono, <duration>s`

Use the automated harness `scripts/rocm_smoke.sh` (see below) for a single-command
equivalent of steps 3b–3d.

---

## 4. Risks and Mitigations

### 4a. flash-attention / bitsandbytes (CUDA-only)

`flash-attention` and `bitsandbytes` are CUDA-only libraries with no ROCm wheel in the
PyPI index.  OmniVoice falls back to **SDPA (Scaled Dot-Product Attention)** when
`flash-attention` is absent — this is the standard PyTorch fallback and is supported on
ROCm via HIP.  There is no code change required; the fallback is automatic.

**Mitigation:** do NOT install `flash-attention` or `bitsandbytes` on knuckles.
Confirm SDPA path by checking that `torch.backends.cuda.flash_sdp_enabled()` does not
raise and that synthesis completes without error.

### 4b. ROCm version mismatch

The ROCm stack on `knuckles` must match the PyTorch-ROCm wheel.  A mismatch causes
`import torch` to fail or GPU init to crash.

**Mitigation:** confirm ROCm version on-node before selecting the wheel (section 1
TODO-confirm-on-node).  Use `rocm-smi` and `rocminfo` as ground truth.

### 4c. HIP device enumeration with dual GPUs

Knuckles carries two R9700 GPUs.  HIP device 0 is assigned by driver enumeration order,
which may not be stable across reboots.

**Mitigation:** after smoke test passes on `cuda:0`, verify HIP device 0 is the
intended GPU (`rocm-smi` device index vs `torch.cuda.get_device_name(0)`).  Set
`OMNIVOICE_DEVICE=cuda:0` or `cuda:1` explicitly in the systemd/container env to pin
the correct device.  Document the chosen assignment in the node's service config.

### 4d. Model download on first run

`k2-fsa/OmniVoice` pulls ~several GB on first load.  Ensure adequate disk on `knuckles`
and HF hub cache set to a data volume (`HF_HOME` env var) to avoid filling the OS disk.

---

## 5. Capacity-Routing Note

`operator_nodes.yaml` cap declarations control which workloads route to which nodes.

| Node | caps | Workloads routed |
|------|------|-----------------|
| `knuckles` | `[rocm, voice]` | `voice.omnivoice` (needs:[voice]) |
| NVIDIA nodes | `[cuda, comfyui, browser, voice]` | all voice + image/video |

Key routing behaviours:

- `voice.omnivoice` declares `needs:[voice]` — it routes to knuckles once this
  seam is validated and the cap is activated in the live routing config.
- Image/video operators (ComfyUI, diffusers) declare `needs:[comfyui]` or
  `needs:[cuda]` and do **not** carry `needs:[rocm]`.  Their CUDA-only installers
  (cu128 torch + CUDA-native custom nodes) correctly refuse to run on `knuckles`
  because the `comfyui` / `cuda` cap is absent from knuckles' cap list — no special
  logic needed.
- The `rocm` cap on knuckles exists as a discriminator for tooling that needs to
  know "this node runs HIP" (e.g. wheel selection scripts, CI matrix).  It is not
  a `needs:` target for production operators at this time.

**Gate before enabling live routing:** all three smoke assertions in section 3 must
pass on `knuckles`.  Record the node hostname, ROCm version, torch+torchaudio version,
and PASS output in a comment on the enabling PR.

---

## References

- `pmoves/services/creator-operator/omnivoice_server.py` — `/healthz` + `/synthesize`
- `pmoves/services/creator-operator/VOICE_ACCEPTANCE.md` — live-verified NVIDIA path,
  direct-model API, env var reference
- `pmoves/services/creator-operator/requirements-prod.txt` — wheel pin to swap
- `pmoves/config/operator_nodes.yaml` — knuckles cap declaration
- `pmoves/services/creator-operator/scripts/rocm_smoke.sh` — automated smoke harness
