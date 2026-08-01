# Engine: `kitten_tts`

> Upstream: KittenTTS (Expresso) — ultra-lightweight TTS, the lowest-latency floor.

## How to test

```bash
# From the TTS Studio host (or any node that can reach :7860)
pterm push "kitten_tts test" --title "TTS"
python pmoves/tools/test_all_tts_engines.py --engine kitten_tts
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_kitten")
c.predict(kitten_voice="expr-voice-2-f", api_name="/synthesize")
# Returns (sample_rate, np.ndarray) for the unified endpoint,
# or (filepath,) for legacy endpoints.
c.predict(api_name="/handle_unload_kitten")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "kitten_tts",
    "name": "KittenTTS",
    "load_api": "/handle_load_kitten",
    "unload_api": "/handle_unload_kitten",
    "load_kwargs": {},
    "synth_kwargs": {"kitten_voice": "expr-voice-2-f"},
}
```

## Available voices

`expr-voice-2-m`, `expr-voice-2-f`, `expr-voice-3-m`, `expr-voice-3-f`,
`expr-voice-4-m`, `expr-voice-4-f`, `expr-voice-5-m`, `expr-voice-5-f`.

## Hardware requirements

- VRAM: ~500MB (CPU-friendly)
- Latency: <200ms per short utterance
- No setup API (model is built into the image)

## Reviewer checklist

- [ ] `kitten_voice` resolves to one of the 8 `expr-voice-*-{m,f}` voices
- [ ] Output is a 24kHz mono WAV
- [ ] No model download required (fail fast if load errors)
- [ ] Default voice `expr-voice-2-f` matches `KITTEN_VOICES` registry

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: voice not found` | Voice not in `KITTEN_VOICES` registry | Update `KITTEN_VOICES` list in `flute-gateway/providers/ultimate_tts.py` |
| `502 Bad Gateway` from gradio_client | TTS Studio not running | `make up-voice` (or `pterm start <launcher>`) |
| Audio plays but is silent | Wrong sample rate (engine emits 16kHz, harness expects 24kHz) | Resample in `validate_wav()` before comparing |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`KITTEN_VOICES`, `ENGINE_NAMES["kitten_tts"]`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 1 in `ENGINES`)
- **Flute `_build_params` slot** — `data[76]` (`kitten_voice`)
- **Pinokio curated app** — `pmoves/configs/pinokio-apps/curated/ultimate-tts-studio.yaml`

## Reviewer notes

_(free-form — capture anything you learned reviewing this engine that future reviewers should know)_

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
