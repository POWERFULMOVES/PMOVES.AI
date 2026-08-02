# Engine: `chatterbox_multilingual`

> Upstream: Chatterbox Multilingual — 17-language synthesis, the widest
> coverage in the chatterbox family.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine chatterbox_multilingual
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_chatterbox_multilingual")
c.predict(
    chatterbox_mtl_language="en",
    chatterbox_mtl_exaggeration=0.5,
    chatterbox_mtl_temperature=0.8,
    chatterbox_mtl_cfg_weight=0.5,
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_chatterbox_multilingual")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "chatterbox_multilingual",
    "name": "Chatterbox Multilingual",
    "load_api": "/handle_load_chatterbox_multilingual",
    "unload_api": "/handle_unload_chatterbox_multilingual",
    "load_kwargs": {},
    "synth_kwargs": {
        "chatterbox_mtl_language": "en",
        "chatterbox_mtl_exaggeration": 0.5,
        "chatterbox_mtl_temperature": 0.8,
        "chatterbox_mtl_cfg_weight": 0.5,
    },
}
```

## Hardware requirements

- VRAM: ~6GB (concurrent mode ok)
- Latency: ~1-2s per short utterance
- No setup API
- Timeout override: 180s (set in `ENGINE_TIMEOUTS`)

## Reviewer checklist

- [ ] `chatterbox_mtl_language` is a valid ISO 639-1 code (one of the 17 supported)
- [ ] `chatterbox_mtl_exaggeration` is in `[0.0, 1.0]`
- [ ] `chatterbox_mtl_temperature` is in `[0.0, 2.0]`
- [ ] `chatterbox_mtl_cfg_weight` is in `[0.0, 1.0]`
- [ ] Output is 24kHz mono WAV
- [ ] Engine prefix `chatterbox_mtl_` matches the upstream app's param naming (not `chatterbox_multilingual_`)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: language not supported` | ISO code not in the 17-language set | Use one of: en, es, fr, de, it, pt, ja, ko, zh, ru, ar, hi, tr, nl, sv, da, fi |
| Long load time | 17-language model is heavier | Bump `ENGINE_TIMEOUTS["chatterbox_multilingual"]` (default 180s) |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["chatterbox_multilingual"] = "Chatterbox Multilingual"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 13 in `ENGINES`)
- **Flute `_build_params` slot** — `data[10-18]` (9 slots)
- **Timeout override** — `ENGINE_TIMEOUTS["chatterbox_multilingual"] = 180.0`

## Reviewer notes

The multilingual variant adds a `chatterbox_mtl_language` parameter that
the other chatterbox variants don't have. The flute-gateway `_build_params`
sets data[10] = language and the rest of the chatterbox_mtl slots for
exaggeration/temperature/cfg_weight.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
