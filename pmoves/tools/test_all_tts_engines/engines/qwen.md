# Engine: `qwen` (Qwen Voice Design)

> Upstream: Alibaba Qwen Voice Design — multilingual voice design via
> natural-language voice description.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine qwen
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(
    model_type="Base",
    model_size="1.7B",
    api_name="/handle_load_qwen",
)
c.predict(
    qwen_mode="voice_design",
    qwen_clone_model_size="1.7B",
    qwen_chunk_size=200,
    qwen_speaker="Ryan",
    qwen_language="Auto",
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_qwen")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "qwen",
    "name": "Qwen Voice Design",
    "load_api": "/handle_load_qwen",
    "unload_api": "/handle_unload_qwen",
    "load_kwargs": {"model_type": "Base", "model_size": "1.7B"},
    "synth_kwargs": {
        "qwen_mode": "voice_design",
        "qwen_clone_model_size": "1.7B",
        "qwen_chunk_size": 200,
        "qwen_speaker": "Ryan",
        "qwen_language": "Auto",
    },
}
```

## Hardware requirements

- VRAM: ~10GB (concurrent mode ok; the 1.7B model)
- Latency: ~3-6s per short utterance
- No setup API
- Timeout override: 240s

## Reviewer checklist

- [ ] `model_size` is in `["0.5B", "1.7B"]` (the upstream app's model table)
- [ ] `qwen_mode` is `voice_design` (the design mode, not clone)
- [ ] `qwen_chunk_size` is in `[50, 1000]`
- [ ] `qwen_speaker` is a valid speaker name (or `Auto`)
- [ ] `qwen_language` is a valid ISO 639-1 code or `Auto`
- [ ] Output is 24kHz mono WAV
- [ ] **Flute `_build_params` slots for qwen (v1 layout) are `data[40, 60, 66, 87, 100]`** — verify against upstream launch.py once accessible

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: model not found` | `model_size` not in the upstream app's table | Use `1.7B` (default) or `0.5B` |
| `KeyError: qwen` in flute | Missing branch in `_build_params` | The 2322 redo added the branch; verify it's there |
| 504 timeout on long text | `qwen_chunk_size` too high | Reduce to 100-200 (test harness default 200) |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["qwen"] = "Qwen Voice Design"`, branch added in PR #2322 redo `79e88313`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 9 in `ENGINES`)
- **Flute `_build_params` slot** — `data[40, 60, 66, 87, 100]` (v1 — see Reviewer notes)
- **Timeout override** — `ENGINE_TIMEOUTS["qwen"] = 240.0`

## Reviewer notes

The 2322 redo added a qwen branch to flute-gateway's `_build_params` with
slots at data[40, 60, 66, 87, 100]. This is a **v1 slot allocation** — the
101-param unified endpoint layout has 9 single-slot gaps that don't fit
qwen's 5 synth params contiguously, so the redo used the available gaps.
Verify against the upstream TTS app's launch.py /gradio_api/info endpoint
for the exact positions; update if the upstream app uses different slots.

Qwen's `load_kwargs` (`model_type` + `model_size`) are sent during the
`/handle_load_qwen` call, NOT in the unified synth call. The
`_build_params` only carries the 5 `qwen_*` synth params.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
