# Engine: `indextts`

> Upstream: IndexTTS — index-based synthesis, fast zero-shot cloning.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine indextts
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_indextts")
c.predict(indextts_temperature=0.8, api_name="/synthesize")
c.predict(api_name="/handle_unload_indextts")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "indextts",
    "name": "IndexTTS",
    "load_api": "/handle_load_indextts",
    "unload_api": "/handle_unload_indextts",
    "load_kwargs": {},
    "synth_kwargs": {"indextts_temperature": 0.8},
}
```

## Hardware requirements

- VRAM: ~4GB (concurrent mode ok)
- Latency: ~1-3s per short utterance
- No setup API

## Reviewer checklist

- [ ] `indextts_temperature` is in `[0.1, 1.0]`
- [ ] Output is a 24kHz mono WAV
- [ ] Engine affinity: prefers the 5090 (the operator's primary indextts host)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| 504 timeout on synthesis | Heavy inference under load | Tune `ENGINE_TIMEOUTS`; the test harness already uses 300s for indextts |
| Wrong sample rate | Upstream change | Resample in `validate_wav()` |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["indextts"] = "IndexTTS"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 10 in `ENGINES`)
- **Flute `_build_params` slot** — `data[38-39]`
- **Host affinity** — `pmoves/configs/tts-engine-capabilities.yaml` (`indextts.preferred: "5090"` per PR #2037)

## Reviewer notes

_(free-form)_

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
