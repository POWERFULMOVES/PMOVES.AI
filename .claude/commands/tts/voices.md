List available TTS voices and engines.

## Usage

Use this command to discover available voices across TTS engines.

## Implementation

1. Query Ultimate-TTS-Studio for available voices:
```bash
curl -s http://localhost:7861/gradio_api/info | jq '.named_endpoints'
```

2. Query flute-gateway voice capabilities:
```bash
curl -s http://localhost:8055/v1/voice/capabilities \
  -H "Authorization: Bearer $FLUTE_API_KEY" | jq '.'
```

3. List engine-specific voices:

**KittenTTS voices:**
- `kitten-female-1` - Natural female voice
- `kitten-male-1` - Natural male voice

**Kokoro voices:**
- `kokoro-jp-female` - Japanese female
- `kokoro-en-female` - English female

**F5-TTS voices:**
- `f5-natural` - Natural prosody
- `f5-expressive` - Expressive style

## Voice Properties

| Property | Description |
|----------|-------------|
| `id` | Unique voice identifier |
| `engine` | TTS engine (kitten, kokoro, f5, etc.) |
| `language` | ISO language code |
| `gender` | male/female/neutral |
| `style` | Voice style (natural, expressive, etc.) |

## Notes

- Voice availability depends on installed engines
- Custom voices can be added via VoxCPM voice cloning
- Prosodic synthesis works with all voices
