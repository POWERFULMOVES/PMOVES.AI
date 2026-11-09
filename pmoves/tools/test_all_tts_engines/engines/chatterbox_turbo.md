# Engine: `chatterbox_turbo`

> Upstream: Chatterbox Turbo — fast multilingual synthesis (faster than
> `chatterbox`, slower than `chatterbox_multilingual`).

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine chatterbox_turbo
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_chatterbox_turbo")
c.predict(
    chatterbox_turbo_exaggeration=0.5,
    chatterbox_turbo_temperature=0.8,
    chatterbox_turbo_cfg_weight=0.5,
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_chatterbox_turbo")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "chatterbox_turbo",
    "name": "Chatterbox Turbo",
    "load_api": "/handle_load_chatterbox_turbo",
    "unload_api": "/handle_unload_chatterbox_turbo",
    "load_kwargs": {},
    "synth_kwargs": {
        "chatterbox_turbo_exaggeration": 0.5,
        "chatterbox_turbo_temperature": 0.8,
        "chatterbox_turbo_cfg_weight": 0.5,
    },
}
```

## Hardware requirements

- VRAM: ~5GB (concurrent mode ok)
- Latency: ~0.5-1.5s per short utterance
- No setup API

## Reviewer checklist

- [ ] `chatterbox_turbo_exaggeration` is in `[0.0, 1.0]`
- [ ] `chatterbox_turbo_temperature` is in `[0.0, 2.0]`
- [ ] `chatterbox_turbo_cfg_weight` is in `[0.0, 1.0]`
- [ ] Output is 24kHz mono WAV
- [ ] Engine prefix `chatterbox_turbo_` matches the upstream app's param naming

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: chatterbox_turbo_exaggeration` | Upstream app param rename | Re-check upstream naming; the test harness matches what the test harness calls, but the upstream may have changed |
| Output is the same as `chatterbox` | The selected engine branch fell through to the wrong slot | Check `flute-gateway/providers/ultimate_tts.py::_build_params` chatterbox_turbo branch |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["chatterbox_turbo"] = "Chatterbox Turbo"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 12 in `ENGINES`)
- **Flute `_build_params` slot** — `data[20-27]` (8 slots)

## Reviewer notes

The turbo variant dropped `chatterbox_chunk_size` from the synth kwargs
(intentionally — turbo streams rather than chunked synthesis). The
remaining 3 params (exaggeration/temperature/cfg_weight) use the
`chatterbox_turbo_` prefix to disambiguate from the base chatterbox.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
