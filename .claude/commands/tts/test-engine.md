Test a single TTS engine with optional GPU metrics tracking via GPU Orchestrator.

## Usage

```
/tts:test-engine <engine_id> [--synth] [--metrics]
```

**Arguments:**
- `engine_id` — Engine to test (e.g., `kitten_tts`, `indextts2`, `kokoro`)
- `--synth` — Also run synthesis (default: load-only)
- `--metrics` — Capture GPU VRAM before/after via GPU Orchestrator (port 8200)

## Implementation

### Load-only test (default)
```bash
python -X utf8 pmoves/tools/test_all_tts_engines.py --engine {{args.engine_id}} --load-only {{#if args.metrics}}--metrics{{/if}}
```

### Load + synthesize test
```bash
python -X utf8 pmoves/tools/test_all_tts_engines.py --engine {{args.engine_id}} {{#if args.metrics}}--metrics{{/if}}
```

## Available Engines

Query the capability registry for the full list:

```bash
python -c "import yaml; d=yaml.safe_load(open('pmoves/configs/tts-engine-capabilities.yaml')); [print(f'  {k:25s} {v[\"name\"]:25s} {v[\"category\"]:20s} ~{v[\"vram_estimate_mb\"]}MB') for k,v in d['engines'].items()]"
```

| Engine ID | Name | Category | VRAM |
|-----------|------|----------|------|
| `kitten_tts` | KittenTTS | preset-voices | ~500MB |
| `kokoro` | Kokoro TTS | preset-voices | ~800MB |
| `higgs` | Higgs Audio | preset-voices | ~1500MB |
| `f5_tts` | F5-TTS | voice-cloning | ~2000MB |
| `fish` | Fish Speech | voice-cloning | ~1500MB |
| `fish_s2` | Fish Speech S2 Pro | voice-cloning | ~2000MB |
| `voxcpm` | VoxCPM | voice-cloning | ~2000MB |
| `indextts` | IndexTTS | voice-cloning | ~1200MB |
| `indextts2` | IndexTTS2 | emotion-control | ~3000MB |
| `chatterbox` | ChatterboxTTS | multilingual | ~2000MB |
| `chatterbox_turbo` | Chatterbox Turbo | multilingual | ~1500MB |
| `chatterbox_multilingual` | Chatterbox Multilingual | multilingual | ~2500MB |
| `qwen` | Qwen3 TTS | multilingual | ~2500MB |
| `vibevoice` | VibeVoice | podcast | ~3000MB |

## GPU Metrics Output (--metrics)

When `--metrics` is passed, the script queries GPU Orchestrator at `http://127.0.0.1:8200/api/gpu/status` before and after loading each engine:

```
  KittenTTS metrics:
    VRAM before:  8,192 MB used / 32,768 MB total (25%)
    VRAM after:   8,692 MB used / 32,768 MB total (27%)
    VRAM delta:   +500 MB
    GPU util:     45% → 62%
    Temperature:  55°C → 58°C
```

Falls back gracefully if GPU Orchestrator is offline.

## Examples

```bash
# Quick load test for VRAM gauging
/tts:test-engine kitten_tts --metrics

# Full load + synthesis test with metrics
/tts:test-engine indextts2 --synth --metrics

# Sequential sweep to gauge cumulative GPU load
/tts:test-engine kitten_tts --metrics
/tts:test-engine kokoro --metrics
/tts:test-engine f5_tts --metrics
```

## Related

- **Registry:** `pmoves/configs/tts-engine-capabilities.yaml` — full engine capability map
- **Bulk test:** `/tts:test-all` — test all 14 engines sequentially
- **Voice personas:** `.claude/context/voice-personas.md` — persona-to-engine mapping
- **Hardware:** `pmoves/docs/AGENTS/HARDWARE_TTS_REQUIREMENTS.md` — prosodic templates
