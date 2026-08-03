# Engine: `voxcpm`

> Upstream: VoxCPM — voice cloning + transcription pipeline.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine voxcpm
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_voxcpm")
c.predict(api_name="/synthesize")  # uses default voxcpm params
c.predict(api_name="/handle_unload_voxcpm")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "voxcpm",
    "name": "VoxCPM",
    "load_api": "/handle_load_voxcpm",
    "unload_api": "/handle_unload_voxcpm",
    "load_kwargs": {},
    "synth_kwargs": {
        "voxcpm_cfg_value": 2.0,
        "voxcpm_inference_timesteps": 10,
        "voxcpm_normalize": True,
        "voxcpm_denoise": True,
    },
}
```

## Hardware requirements

- VRAM: ~8GB (concurrent mode ok)
- Latency: ~2-5s per short utterance
- No setup API
- Timeout override: 240s

## Reviewer checklist

- [ ] `voxcpm_cfg_value` is in `[0.5, 5.0]`
- [ ] `voxcpm_inference_timesteps` is in `[1, 50]`
- [ ] `voxcpm_normalize` and `voxcpm_denoise` are booleans
- [ ] Output is 24kHz mono WAV
- [ ] `voxcpm_denoise=True` works on noisy reference audio

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: invalid cfg value` | `voxcpm_cfg_value` out of range | Clamp to `[0.5, 5.0]` in flute-gateway |
| Slow synthesis | Too many timesteps | Reduce `voxcpm_inference_timesteps` (default 10) |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["voxcpm"] = "VoxCPM"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 7 in `ENGINES`)
- **Flute `_build_params` slot** — `data[78-86]` (9 slots)
- **Timeout override** — `ENGINE_TIMEOUTS["voxcpm"] = 240.0`

## Reviewer notes

The voxcpm engine combines voice cloning + automatic transcription. The
denoise+normalize params are post-processing flags that run on the input
reference audio before TTS.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
