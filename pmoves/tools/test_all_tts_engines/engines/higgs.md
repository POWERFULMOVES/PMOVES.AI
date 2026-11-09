# Engine: `higgs` (Higgs Audio)

> Upstream: Higgs Audio — streaming-capable TTS with system prompt control.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine higgs
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_higgs")
c.predict(
    higgs_voice_preset="EMPTY",
    higgs_system_prompt="Read the following text naturally and clearly.",
    higgs_temperature=1.0,
    higgs_top_p=0.95,
    higgs_top_k=50,
    higgs_max_tokens=1024,
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_higgs")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "higgs",
    "name": "Higgs Audio",
    "load_api": "/handle_load_higgs",
    "unload_api": "/handle_unload_higgs",
    "load_kwargs": {},
    "synth_kwargs": {
        "higgs_voice_preset": "EMPTY",
        "higgs_system_prompt": "Read the following text naturally and clearly.",
        "higgs_temperature": 1.0,
        "higgs_top_p": 0.95,
        "higgs_top_k": 50,
        "higgs_max_tokens": 1024,
    },
}
```

## Hardware requirements

- VRAM: ~8GB (concurrent mode ok)
- Latency: ~1-2s per short utterance (streaming-friendly)
- No setup API
- Timeout override: 240s

## Reviewer checklist

- [ ] `higgs_voice_preset` is a valid preset (default `EMPTY` for no preset)
- [ ] `higgs_system_prompt` is a non-empty string (the engine uses it as a contextual instruction)
- [ ] `higgs_temperature` is in `[0.0, 2.0]`
- [ ] `higgs_top_p` is in `[0.0, 1.0]`
- [ ] `higgs_top_k` is in `[1, 200]`
- [ ] `higgs_max_tokens` is in `[64, 4096]`
- [ ] Output is 24kHz mono WAV
- [ ] **No `higgs_audio` alias usage** — the canonical key is `higgs` (alias renamed in PR #2322 redo `79e88313`)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `KeyError: higgs_audio` | Old engine key in flute-gateway | The 2322 redo renamed `higgs_audio` → `higgs`; check `flute-gateway/providers/ultimate_tts.py` |
| 504 timeout on long text | `higgs_max_tokens` too low | Bump to 2048+ (test harness default 1024); tune `ENGINE_TIMEOUTS["higgs"]` (default 240s) |
| `RuntimeError: voice preset not found` | Preset name changed in upstream | Update test harness + flute-gateway with the new preset list |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["higgs"] = "Higgs Audio"`, branch key `higgs` per PR #2322 redo)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 8 in `ENGINES`)
- **Flute `_build_params` slot** — `data[67-75]` (9 slots)
- **Timeout override** — `ENGINE_TIMEOUTS["higgs"] = 240.0`

## Reviewer notes

The 2322 redo renamed `higgs_audio` → `higgs` to match the canonical
internal key in `ENGINE_NAMES`, `ENGINE_TIMEOUTS`, `endpoint_map`, and
`get_engines`. Reviewer thread 3694589703 flagged the mismatch.

The 6 synth params (voice_preset, system_prompt, temperature, top_p,
top_k, max_tokens) are ALL the params the upstream app's `/synthesize`
endpoint accepts for Higgs. The flute-gateway branch sets all 6.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
