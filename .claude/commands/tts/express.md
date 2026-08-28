Expressive TTS synthesis with automatic engine selection based on intent.

## Usage

```
/tts:express <text> [--intent <intent>] [--modifier <mod>] [--ref-audio <path>] [--language <lang>]
```

## Intents

| Intent | Engine | What it does |
|--------|--------|-------------|
| `narrate` | Kokoro | Clear narration with speed control |
| `emote` | IndexTTS2 | 8-dimensional emotion vector (happy, angry, sad, etc.) |
| `dramatic` | Chatterbox | Theatrical delivery with exaggeration control |
| `clone` | F5-TTS | Voice cloning from reference audio |
| `multilingual` | Chatterbox MTL | 17-language synthesis |
| `podcast` | VibeVoice | Multi-speaker dialogue |
| `persona` | Qwen3 | Design a voice from text/preset |
| `agent` | KittenTTS | Ultra-fast for CLI/agent responses |
| `bpm_sync` | F5-TTS | Beat-synchronized for music/DJ |

## Implementation

1. **Load expressions registry:**
```bash
EXPR_FILE="pmoves/configs/tts-engine-expressions.yaml"
```

2. **Resolve intent to engine + params:**
   - Parse `--intent` (default: `narrate`)
   - Look up `intents.<intent>.primary` for engine ID
   - Load `intents.<intent>.params` as base params
   - If `--modifier` given, overlay `intents.<intent>.modifiers.<mod>` params
   - Check `requires` — if `ref_audio` required, verify `--ref-audio` provided

3. **Ensure TTS is running:**
```bash
# Use pterm to check/start
pterm status Ultimate-TTS-Studio.git
# If offline, start it
pterm run "D:\pinokio\api\Ultimate-TTS-Studio.git"
```

4. **Select the correct engine tab in Gradio:**
```python
from gradio_client import Client
client = Client("https://7860.localhost")

# Switch to the target engine
client.predict(engine_name, api_name="/handle_tts_engine_change")
```

5. **Load the engine model (if not already loaded):**
```python
# Each engine has a load handler: /handle_load_<engine_id>
client.predict(api_name=f"/handle_load_{engine_id}")
```

6. **Synthesize with resolved params:**
```python
# Most engines use the unified endpoint
result = client.predict(
    text,           # input text
    ref_audio,      # reference audio (None if not cloning)
    ref_text,       # reference text (empty string if none)
    *engine_params, # engine-specific params from registry
    api_name="/generate_unified_tts"
)
```

7. **Return result:**
   - Audio file path from Gradio
   - Engine used + params applied
   - Duration and GPU metrics if available

## Modifier Examples

```bash
# Happy narration
/tts:express "Welcome to the show!" --intent emote --modifier happy

# Theatrical dramatic reading
/tts:express "To be or not to be" --intent dramatic --modifier theatrical

# Voice clone with tight timing
/tts:express "Clone test" --intent clone --modifier tight --ref-audio /path/to/voice.wav

# Spanish synthesis
/tts:express "Hola mundo" --intent multilingual --language es

# Fast agent response
/tts:express "Task complete" --intent agent

# BPM-synced DJ drop
/tts:express "Drop the bass" --intent bpm_sync --modifier fast_tempo
```

## Cross-References

- **Engine registry:** `pmoves/configs/tts-engine-expressions.yaml`
- **Engine capabilities:** `pmoves/configs/tts-engine-capabilities.yaml`
- **Prosodic templates:** `pmoves/configs/tts-prosodic-templates.yaml`
- **BPM encoding:** `/chit:bpm` (encode prosodic markers before synthesis)
- **Voice status:** `/voice:status` (check Flute-Gateway + TTS health)
- **Skill pairing:** `voice-synthesis` in `pmoves/configs/skill-pairings.yaml`

## Notes

- First synthesis per engine may be slow due to model loading (~10-30s)
- GPU VRAM is shared across loaded engines — check `/gpu:status` for budget
- 3 legacy engines (Fish S1, IndexTTS, Higgs) are accessible via manual engine selection in the Gradio UI but not mapped to intents (superseded by better versions)
- VibeVoice podcast intent uses `/handle_vibevoice_generation`, not the unified endpoint
