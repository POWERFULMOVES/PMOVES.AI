# Engine: `vibevoice` (VibeVoice)

> Upstream: VibeVoice — style transfer synthesis via a separate panel
> (`handle_vibevoice_generation`), NOT the unified `/generate_unified_tts`
> endpoint.

## How to test

```bash
# VibeVoice uses a separate panel - the unified synth endpoint will
# raise UltimateTTSError. The test harness handles this by:
#   1. calling /handle_vibevoice_download (setup_api, downloads model)
#   2. calling /handle_vibevoice_load (load_api)
#   3. skipping the unified synth (synth_kwargs: None)
#   4. calling /handle_vibevoice_unload
python pmoves/tools/test_all_tts_engines.py --engine vibevoice
```

Or via the gradio_client directly (the supported path):

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_vibevoice_download")   # download model
c.predict(
    selected_model_path="models\\VibeVoice-1.5B",
    api_name="/handle_vibevoice_load",
)
c.predict(text=..., api_name="/handle_vibevoice_generation")
c.predict(api_name="/handle_vibevoice_unload")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "vibevoice",
    "name": "VibeVoice",
    "setup_api": "/handle_vibevoice_download",   # download model first
    "load_api": "/handle_vibevoice_load",
    "unload_api": "/handle_vibevoice_unload",
    "load_kwargs": {"selected_model_path": "models\\VibeVoice-1.5B"},
    "synth_kwargs": None,  # Separate endpoint - skip unified synth
}
```

## Hardware requirements

- VRAM: ~6GB (the 1.5B model)
- Latency: ~2-4s per short utterance
- Setup: **mandatory** — model download via `setup_api`
- Style-transfer: voices can be derived from reference audio (style cloning)

## Reviewer checklist

- [ ] `setup_api` (model download) is called BEFORE `load_api`
- [ ] `selected_model_path` points to a valid model directory
- [ ] The test harness correctly skips the unified synth (synth_kwargs=None)
- [ ] `flute-gateway/providers/ultimate_tts.py::_build_params` raises
      `UltimateTTSError` for `engine="vibevoice"` (rejects the unified endpoint)
- [ ] Engine affinity: prefers SPARK (128GB unified memory) for the 1.5B model

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `UltimateTTSError: vibevoice is not supported via the unified endpoint` | User called the test harness's default synth path | This is **expected** — the test harness skips the unified synth. If you need actual synthesis, call `/handle_vibevoice_generation` directly. |
| `FileNotFoundError: model not found` | `setup_api` not called | Run `/handle_vibevoice_download` first |
| OOM on smaller nodes | 1.5B model is heavy | Use `VibeVoice-0.5B` if available; route to SPARK (128GB headroom) via `host_affinity` |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["vibevoice"] = "VibeVoice"`, branch added in PR #2322 redo `79e88313` — raises `UltimateTTSError` for the unified endpoint)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 14 in `ENGINES`)
- **Flute `_build_params` slot** — **N/A** (raises `UltimateTTSError`; the unified endpoint doesn't support vibevoice)
- **Separate panel** — `/handle_vibevoice_generation` (call directly via gradio_client)

## Reviewer notes

The 2322 redo made a deliberate design call: **reject vibevoice
explicitly in the unified `_build_params`** rather than silently
corrupting it with all-None params. Per the test harness's comment
"Synthe_kwargs: None # Separate endpoint - skip unified synth", a silent
no-parameter request through the unified endpoint is the worst possible
outcome — the engine's actual synth API is `/handle_vibevoice_generation`,
not the unified endpoint. The error message in the redo tells the
caller exactly that.

If you want to add vibevoice back to the unified endpoint, the upstream
TTS app's launch.py would need to expose the vibevoice params as
positional slots in `/generate_unified_tts`. That's an upstream change,
not a flute-gateway change.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
