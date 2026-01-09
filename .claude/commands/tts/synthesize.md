Synthesize text to speech using the TTS pipeline.

## Usage

Use this command to generate audio from text using Ultimate-TTS-Studio or flute-gateway.

## Implementation

1. Check TTS service health:
```bash
curl -f http://localhost:7861/gradio_api/info
```

2. For flute-gateway prosodic synthesis:
```bash
curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FLUTE_API_KEY" \
  -d '{
    "text": "Hello, this is a test.",
    "voice": "default",
    "format": "wav"
  }'
```

3. For Ultimate-TTS-Studio direct access:
```bash
# Use the Gradio API client
python -c "
from gradio_client import Client
client = Client('http://localhost:7861')
result = client.predict(
    text='Hello world',
    voice='default',
    api_name='/synthesize'
)
print(result)
"
```

## Output Formats

- `wav` - Uncompressed (best quality)
- `mp3` - Compressed (smaller files)
- `ogg` - Open format (web compatible)

## Notes

- First synthesis may be slow due to model loading
- GPU acceleration significantly improves performance
- Prosodic synthesis adds natural pauses and emphasis
