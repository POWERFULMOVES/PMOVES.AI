# Engine: `fish_s2` (Fish Speech S2 Pro)

> Upstream: Fish Speech S2 Pro — 13-language zero-shot, the multilingual Fish.

## How to test

```bash
# S2 Pro needs repo clone + weight download first. The test harness runs
# /handle_setup_fish_s2 (setup_api) before /handle_load_fish_s2.
python pmoves/tools/test_all_tts_engines.py --engine fish_s2
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_setup_fish_s2")   # clone repo + download weights
c.predict(api_name="/handle_load_fish_s2")
c.predict(
    fish_s2_temperature=0.8,
    fish_s2_top_p=0.8,
    fish_s2_repetition_penalty=1.1,
    fish_s2_max_tokens=2048,
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_fish_s2")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "fish_s2",
    "name": "Fish Speech S2 Pro",
    "setup_api": "/handle_setup_fish_s2",   # clone repo + download ~4.56B params
    "load_api": "/handle_load_fish_s2",
    "unload_api": "/handle_unload_fish_s2",
    "load_kwargs": {},
    "synth_kwargs": {
        "fish_s2_temperature": 0.8,
        "fish_s2_top_p": 0.8,
        "fish_s2_repetition_penalty": 1.1,
        "fish_s2_max_tokens": 2048,
    },
}
```

## Hardware requirements

- VRAM: ~10GB (concurrent mode ok)
- Latency: ~3-8s per short utterance
- Setup: **mandatory** — repo clone + ~4.5B param download via `setup_api`
- Timeout override: 300s (the longest in the engine set)

## Reviewer checklist

- [ ] `setup_api` is called BEFORE `load_api` (otherwise model file is missing)
- [ ] `fish_s2_max_tokens` is in `[256, 2048]` (the engine's hard cap)
- [ ] `fish_s2_repetition_penalty` is in `[0.5, 2.0]`
- [ ] Output is 24kHz mono WAV
- [ ] Flute `_build_params` slots for fish_s2 (v1 layout) are `data[9, 19, 30, 37]` — verify against upstream launch.py once accessible

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: model.bin` | `setup_api` not called or failed | Run `handle_setup_fish_s2` first; check network/disk |
| 504 timeout | 4.56B params load is slow | Bump `ENGINE_TIMEOUTS["fish_s2"]` (default 300s — already the highest) |
| `KeyError: fish_s2` in flute | Missing branch in `_build_params` | The 2322 redo added the branch; verify it's there |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["fish_s2"] = "Fish Speech S2 Pro"`, branch added in PR #2322 redo `79e88313`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 11 in `ENGINES`)
- **Flute `_build_params` slot** — `data[9, 19, 30, 37]` (v1 — see Reviewer notes)
- **Timeout override** — `ENGINE_TIMEOUTS["fish_s2"] = 300.0`

## Reviewer notes

The 2322 redo added a fish_s2 branch to flute-gateway's `_build_params` with
slots at data[9, 19, 30, 37]. This is a **v1 slot allocation** — the 101-param
unified endpoint layout has 9 single-slot gaps that don't fit fish_s2's 4
synth params contiguously, so the redo used the available gaps. Verify
against the upstream TTS app's launch.py /gradio_api/info endpoint for the
exact positions; update if the upstream app uses different slots.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
