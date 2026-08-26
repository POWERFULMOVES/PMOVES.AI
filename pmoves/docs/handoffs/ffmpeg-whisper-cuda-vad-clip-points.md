# ffmpeg-whisper — CUDA, VAD, and the clip-point ceiling

**Lane:** 4090-claude (field) · **Date:** 2026-08-04 · **Branch:** `fix/ffmpeg-whisper-cuda-vad-clip-points`

## Goal, not just the bug

The deliverable is **clip points** — segment boundaries used for reels, soundbites and source
verification. A boundary error is a bad cut or a misquote, so *where* the cuts land is the
product; the transcript text is secondary.

That reframes what "fixed" means. Three things must all hold, and the previous work had none:

1. transcription runs on the GPU (it silently ran on CPU at 0.24× realtime)
2. boundaries are **speech-derived**, not mechanical (no VAD model shipped at all)
3. a boundary can be **as long as the soundbite** (this is the one nobody had found)

## The ceiling nobody found: `queue`

Verified against FFmpeg source at the pinned tag
(`libavfilter/af_whisper.c`, `whisper_options[]`, n8.1.2):

| Option | Default | Note |
|---|---|---|
| `queue` | `3000000` µs = **3 s** | buffer size; transcription fires on saturation |
| `use_gpu` | `1` (**true**) | GPU is requested by default |
| `vad_model` | *(unset)* | no VAD unless supplied |
| `vad_threshold` | `0.5` | |
| `vad_min_speech_duration` | `100000` µs = 0.1 s | |
| `vad_min_silence_duration` | `500000` µs = 0.5 s | |

Without `vad_model`, the filter transcribes when `audio_buffer_fill_size >=
audio_buffer_queue_size` — i.e. **fixed windows sized by `queue`**. That is the source of the
mechanical seams measured earlier (boundaries landing at exact `duration ÷ queue` intervals,
with the boundary word-duplications sitting on those seams).

**The trap:** `queue` bounds segment length even when VAD is working. With the 3 s default, a
17.1 s soundbite is *unreachable* — the buffer saturates and forces a cut at 3 s no matter how
`vad_min_silence_duration` is tuned. Earlier VAD A/B testing concluded "VAD barely moved the
median"; the likelier explanation is that `queue` was the binding constraint the whole time.

So: **raise `queue` above the longest soundbite you intend to cut, then tune VAD.** Tuning VAD
under a low `queue` measures nothing.

## `use_gpu` defaults true — which is why this was invisible

`use_gpu` defaults to `1`. The GPU was always requested; the build simply had no CUDA backend
to give it, so it silently fell back to CPU and ffmpeg exited **0** throughout. Nothing in the
logs said "degraded". Measured: 2789 s of wall time for 669.55 s of audio = **0.24× realtime**
on a 4090.

Root cause: the cmake never passed the CUDA flag, so `libwhisper.so` linked `libggml-cpu` only
and `libggml-cuda.so` was absent from the image.

This change adds `-DGGML_CUDA=1` (the form whisper.cpp's own README documents) **and** a
`test -f /usr/local/lib/libggml-cuda.so` guard, so a build that would have shipped CPU-only
fails loudly at build time instead of silently at runtime.

## Why configure failed before, and why the error lied

The prior CUDA attempt died at:

    ERROR: whisper >= 1.7.5 not found using pkg-config

That message is misleading. From FFmpeg `configure` (n8.1.2):

- line 7398 — `require_pkg_config whisper "whisper >= 1.7.5" whisper.h whisper_init_from_file_with_params`
- `test_pkg_config` (line 1597) does **two** things: `pkg-config --exists` (line 1606), then
  `check_func_headers` (line 1610), which is a **compile-and-link test** using pkg-config's
  cflags/libs

Both failures print the same "not found using pkg-config" text. The package was found; the
**link** failed, because enabling CUDA gave `libwhisper.so` dependencies that the generated
`whisper.pc` does not carry.

Fix: set `PKG_CONFIG_PATH` and add `-L` search paths for `/usr/local/lib` and the CUDA libdir.
Deliberately **not** forcing `--extra-libs="-lggml-cuda -lcudart -lcublas"` — with
`BUILD_SHARED_LIBS=ON` the linker follows `DT_NEEDED`, and hardcoded library names are brittle
(a single wrong name kills configure). Add them only if the link actually fails.

## Layer split — and the disk incident

The whole stage was one `RUN`: whisper.cpp clone/build/install, then ffmpeg clone/configure/
build, then a ~3.1 GB model download. Docker caches per-`RUN`, so a failure in the *last* step
re-ran the *first* — every failed ffmpeg configure re-compiled whisper.cpp (~41 min) and
re-downloaded 3.1 GB. That produced **39 GB of build cache** and contributed to the 2026-08-04
disk-full event that took the Docker daemon down.

Now four layers, least-volatile first (models → whisper.cpp → ffmpeg), so a failing configure
costs a configure.

## Do not add the CUDA compat directory to LD_LIBRARY_PATH

Verified on this node: `nvidia/cuda:12.6.2-cudnn-runtime-ubuntu22.04` ships
`/usr/local/cuda/compat/libcuda.so.560.35.03`, but it is **not** on `LD_LIBRARY_PATH` and
**not** in `ld.so.conf.d`, so `ldconfig` correctly resolves `libcuda.so.1` to the WSL-injected
shim at `/usr/lib/x86_64-linux-gnu`. This image is therefore safe as written.

It is one edit away from not being safe. The upstream `ghcr.io/ggml-org/whisper.cpp:main-cuda`
image prepends `/usr/local/cuda-13.0/compat` and, on a Windows/WSL node, that compat `libcuda`
shadows the shim: CUDA reports *"no CUDA-capable device is detected"*, falls back to CPU, and
still exits 0.

Measured on the 4090 (driver 591.44, compute 8.9):

| `LD_LIBRARY_PATH` | Result |
|---|---|
| upstream default | `no CUDA-capable device is detected` → CPU, exit 0 |
| compat excluded | `found 1 CUDA devices ... compute capability 8.9`, `using CUDA0 backend` |

A CUDA 12.6.2 container on the same node reports `DEVICE_COUNT=1 ERR=0`, so GPU-in-Docker is
otherwise healthy. The host driver (591.44) is *newer* than the compat lib, so the compat layer
was never needed here — only harmful.

**This is an empirical finding, not documented NVIDIA guidance.** The WSL user guide does not
discuss forward-compatibility packages; it does say the Windows driver is "stubbed inside WSL 2
as `libcuda.so`" and that you "must not install any NVIDIA GPU Linux driver within WSL 2".
This is that rule reached via `LD_LIBRARY_PATH` instead of an install. Likely affects **any**
compat-prepending CUDA image on **any** Windows/WSL node in the fleet. Tell: `nvidia-smi` works
inside the container while the CUDA runtime reports no device.

## Models are baked as a floor, not as truth

Both models are baked so the image is useful offline and so a cold node is not blocked on a
download — but the ASR model is an `ARG`, and both paths are exposed as env so callers override
rather than hardcode. Model selection belongs to the catalog/registry layer that tracks what is
current, not to this Dockerfile. Baking a default is a floor; it is not a claim about which
model is right.

VAD model: `ggml-org/whisper-vad`, MIT, `ggml-silero-v5.1.2.bin`, verified on the Hub at
885,098 bytes.

## Deliberately out of scope

- **Spec-vs-implementation drift.** `pmoves/docs/PMOVES.AI PLANS/PMOVES.ffmpeg/pmoves_orchestration_mesh_repo_scaffold.md`
  specifies this service as an HTTP shim that shells out to `ffmpeg -af whisper=...`. The current
  `server.py` instead uses faster-whisper (`WhisperModel(...)` pulls CTranslate2 weights from HF
  by name at runtime) and never invokes the filter. The image currently pays for both paths.
  That is an operator decision about which side is authoritative — not something to resolve by
  silently deleting either one.
- `DEFAULT_WHISPER_MODEL = "small"` (`server.py:324`) contradicts this service's CLAUDE.md
  ("Default: large-v3"). It governs the path that actually executes.
- CI matrix uses `context: ./pmoves/services/ffmpeg-whisper`, which cannot satisfy this
  Dockerfile's `COPY pmoves/...` paths — **the service cannot build in CI**. Compose is already
  correct (`context: ..`); only CI is wrong.
- `CUDA_VERSION=12.6.2` vs the fleet-standard 12.8.1 / repo-owned `pmoves/cuda-base`. Note that
  the 5090 is sm_120 and **cannot** be covered until that bump lands — Blackwell needs CUDA ≥ 12.8.
