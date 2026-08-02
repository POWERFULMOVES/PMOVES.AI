# Engine: `chatterbox`

> Upstream: ChatterboxTTS — expressive narration, the operator's default
> expressive engine on the 5090.

## How to test

```bash
python pmoves/tools/test_all_tts_engines.py --engine chatterbox
```

Or via the gradio_client directly:

```python
from gradio_client import Client
c = Client("http://127.0.0.1:7860")
c.predict(api_name="/handle_load_chatterbox")
c.predict(
    chatterbox_exaggeration=0.5,
    chatterbox_temperature=0.8,
    chatterbox_cfg_weight=0.5,
    chatterbox_chunk_size=300,
    api_name="/synthesize",
)
c.predict(api_name="/handle_unload_chatterbox")
```

## Canonical synth kwargs (from `pmoves/tools/test_all_tts_engines.py`)

```python
{
    "id": "chatterbox",
    "name": "ChatterboxTTS",
    "load_api": "/handle_load_chatterbox",
    "unload_api": "/handle_unload_chatterbox",
    "load_kwargs": {},
    "synth_kwargs": {
        "chatterbox_exaggeration": 0.5,
        "chatterbox_temperature": 0.8,
        "chatterbox_cfg_weight": 0.5,
        "chatterbox_chunk_size": 300,
    },
}
```

## Hardware requirements

- VRAM: ~6GB (concurrent mode ok)
- Latency: ~1-3s per short utterance
- No setup API
- **Default voice engine** for flute-gateway's expressive tier (per
  `pmoves/configs/tts-engine-capabilities.yaml`)

## Reviewer checklist

- [ ] `chatterbox_exaggeration` is in `[0.0, 1.0]` (the upstream app's hard cap)
- [ ] `chatterbox_temperature` is in `[0.0, 2.0]`
- [ ] `chatterbox_cfg_weight` is in `[0.0, 1.0]`
- [ ] Output is 24kHz mono WAV
- [ ] Host affinity: 5090 preferred (per `pmoves/configs/tts-engine-capabilities.yaml`)

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: exaggeration out of range` | Upstream app version drift | Pin to tested upstream version (`pmoves/configs/pinokio-apps/curated/ultimate-tts-studio.yaml::version_seen`) |
| OOM on 5090 | Other engines competing for VRAM | Check `gpu_reservation_mb` for the TTS Studio; reload via pterm |

## File locations

- **Flute provider** — `pmoves/services/flute-gateway/providers/ultimate_tts.py` (`ENGINE_NAMES["chatterbox"] = "ChatterboxTTS"`)
- **Test harness** — `pmoves/tools/test_all_tts_engines.py` (entry 6 in `ENGINES`)
- **Flute `_build_params` slot** — `data[4-8]`
- **Default in test harness** — yes, the FIRST `chatterbox` branch in the chatterbox family
- **Operator default** — yes, for `flute-gateway`'s default engine

## Reviewer notes

The chatterbox family has 3 variants: `chatterbox`, `chatterbox_turbo`,
`chatterbox_multilingual`. They share `ENGINE_NAMES["chatterbox*"]` but
have distinct synth kwargs. Per PR #2322 redo, the unified `_build_params`
only sets the params for the selected engine — see the `engine in
("chatterbox", "chatterbox_turbo", "chatterbox_multilingual")` block.

---
*Last reviewed: 2026-08-01 (TTS test README redo)*
