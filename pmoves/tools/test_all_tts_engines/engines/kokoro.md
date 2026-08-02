# Engine: `kokoro`

> Upstream: Kokoro ONNX — multilingual TTS, the default CPU floor when expressive
> engines are OOM or down.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine kokoro
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_kokoro")
c.predict(kokoro_voice="af_bella", kokoro_speed=1.0, api_name="/synthesize")
c.predict(api_name="/handle_unload_kokoro")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "kokoro",
    "name": "Kokoro TTS",
    "load_api": "/handle_load_kokoro",
    "unload_api": "/handle_unload_kokoro",
    "load_kwargs": {},
    "synth_kwargs": {"kokoro_voice": "af_heart", "kokoro_speed": 1.0},
}
```

## Available voices

`af_bella`, `af_heart`, `af_nova`, etc. (English), plus other locales in
the upstream app's voice table. Default voice in the test harness is
`af_heart`.

## Hardware requirements

- VRAM: ~500MB (CPU-friendly)
- Latency: <300ms per short utterance
- No setup API

## Reviewer checklist

- [ ] `kokoro_voice` resolves to a valid voice (the upstream app's `kokoro_voice_dropdown` choices)
- [ ] `kokoro_speed` is in `[0.5, 2.0]`
- [ ] Output is a 24kHz mono WAV
- [ ] CPU-floor fallback works: if expressive tier is down, flute-gateway falls through to kokoro

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `Could not find voice` | Locale not installed in the upstream image | Pull a multi-locale Kokoro build or restrict voices to the image's locale set |
| Output speed too fast/slow | `kokoro_speed` out of range | Clamp to `[0.5, 2.0]` in flute-gateway |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`DEFAULT_VOICES["kokoro"] = "af_bella"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 2 in `ENGINES`)
- **Flute `_build_params` slot** — `data[28] = voice`, `data[29] = 1.0`
- **CPU floor** — `pmoves/services/flute-gateway/persona_selector.py::resolve_engine_host` falls through to kokoro if no expressive engine is up

## Reviewer notes

_(free-form)_

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
