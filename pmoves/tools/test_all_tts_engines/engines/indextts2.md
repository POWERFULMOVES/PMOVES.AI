# Engine: `indextts2`

> Upstream: IndexTTS2 — emotion vector control. Successor to indextts.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine indextts2
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_indextts2")
c.predict(
    indextts2_emotion_mode="audio_reference",
    indextts2_calm=1.0,
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_indextts2")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "indextts2",
    "name": "IndexTTS2",
    "load_api": "/handle_load_indextts2",
    "unload_api": "/handle_unload_indextts2",
    "load_kwargs": {},
    "synth_kwargs": {
        "indextts2_emotion_mode": "audio_reference",
        "indextts2_calm": 1.0,
    },
}
```

## Hardware requirements

- VRAM: ~6GB (concurrent mode ok)
- Latency: ~1-3s per short utterance
- No setup API
- Timeout override: 180s (set in `ENGINE_TIMEOUTS`)

## Reviewer checklist

- [ ] `indextts2_emotion_mode` is one of `["audio_reference", "text", "vector"]`
- [ ] `indextts2_calm` is in `[0.0, 2.0]`
- [ ] Output is a 24kHz mono WAV
- [ ] Engine affinity: prefers the 5090 (replaces the older indextts's slot)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: emotion mode not found` | Upstream app version mismatch | Pin to a tested upstream version (see `pmoves/configs/pinokio-apps/curated/ultimate-tts-studio.yaml::version_seen`) |
| Slow first load | Model warm-up | Bump `ENGINE_TIMEOUTS["indextts2"]` (default 180s) |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["indextts2"] = "IndexTTS2"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 4 in `ENGINES`)
- **Flute `_build_params` slot** — `data[41-59]` (uses 9 slots, the most of any engine)
- **Timeout override** — `ENGINE_TIMEOUTS["indextts2"] = 180.0`

## Reviewer notes

_(free-form)_

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
