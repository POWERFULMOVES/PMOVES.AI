# Engine: `f5_tts`

> Upstream: F5-TTS — high-quality voice cloning with reference audio.

## How to test

```bash
# F5-TTS needs model download before first load. The test harness runs
# /handle_f5_download automatically when setup_api is set.
python pmoves/tools/test_all_tts_engines.py --engine f5_tts
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_f5_download")  # download model
c.predict(model_name="F5-TTS Base", api_name="/handle_f5_load")
c.predict(f5_speed=1.0, api_name="/synthesize")
c.predict(api_name="/handle_f5_unload")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "f5_tts",
    "name": "F5-TTS",
    "setup_api": "/handle_f5_download",   # model download required
    "load_api": "/handle_f5_load",
    "unload_api": "/handle_f5_unload",
    "load_kwargs": {"model_name": "F5-TTS Base"},
    "synth_kwargs": {"f5_speed": 1.0},
}
```

## Hardware requirements

- VRAM: ~6GB (concurrent mode ok)
- Latency: ~2-5s per short utterance
- Setup: model download (~2GB) on first run

## Reviewer checklist

- [ ] `setup_api` (model download) is called BEFORE `load_api` (model load)
- [ ] `f5_speed` is in `[0.5, 2.0]`
- [ ] Output sample rate matches the upstream TTS app's F5 default (24kHz)
- [ ] Engine `ENGINE_TIMEOUTS["f5_tts"]` is set to ≥180s for the first-load window

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: model not found` | `setup_api` not called | Run `/handle_f5_download` first; check test harness order |
| 504 timeout on first load | First-time model load is slow | Tune `ENGINE_TIMEOUTS["f5_tts"]` (default 180s) |
| `RuntimeError: out of memory` | GPU OOM | Switch to host_affinity fallthrough; reduce `min_vram_mb` or use `f5_tts_v2_small` |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`DEFAULT_VOICES["f5_tts"] = None`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 3 in `ENGINES`)
- **Flute `_build_params` slot** — `data[61-65]`
- **Timeout override** — `pmoves/services/flute-gateway/providers/ultimate_tts.py::ENGINE_TIMEOUTS["f5_tts"] = 180.0`

## Reviewer notes

_(free-form)_

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
