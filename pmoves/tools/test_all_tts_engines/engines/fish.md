# Engine: `fish` (Fish Speech S1)

> Upstream: Fish Speech S1 — zero-shot voice cloning, the original Fish.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine fish
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_fish")
c.predict(api_name="/synthesize")  # uses default empty reference + S1 params
c.predict(api_name="/handle_unload_fish")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "fish",
    "name": "Fish Speech S1",
    "load_api": "/handle_load_fish",
    "unload_api": "/handle_unload_fish",
    "load_kwargs": {},
    "synth_kwargs": {},  # empty — S1 has no extra synth params
}
```

## Hardware requirements

- VRAM: ~4GB (concurrent mode ok)
- Latency: ~2-4s per short utterance
- No setup API

## Reviewer checklist

- [ ] Engine loads cleanly (S1 model is small, should fit in any node)
- [ ] Output is the upstream app's default Fish S1 sample rate
- [ ] No `fish_speech` alias usage — the canonical key is `fish` (alias dropped in PR #2322 redo)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: fish_speech` | Old engine key in flute-gateway | The 2322 redo renamed `fish_speech` → `fish`; check `flute-gateway/providers/ultimate_tts.py` |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["fish"] = "Fish Speech S1"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 5 in `ENGINES`)
- **Flute `_build_params` slot** — `data[31-36]`
- **Alias history** — the `fish_speech` alias was removed in PR #2322 redo commit `79e88313` (operator review thread 3694589703)

## Reviewer notes

_(free-form)_

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
