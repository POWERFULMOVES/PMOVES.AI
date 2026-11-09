Synthesize speech via Flute-Gateway's prosodic API.

Flute-Gateway provides multimodal voice synthesis with natural prosody (pauses, emphasis, intonation). This command triggers text-to-speech synthesis using the prosodic engine.

## Usage

Run this command with text to synthesize:
- `/voice:synthesize Hello, welcome to PMOVES` - Basic synthesis
- `/voice:synthesize --voice aria "Important announcement"` - Specific voice

## Implementation

Execute the following steps:

1. **Check Flute-Gateway health:**
   ```bash
   curl -sf http://localhost:8055/healthz | jq .
   ```

   If not healthy, check if Ultimate-TTS-Studio is running on port 7861.

2. **Synthesize with prosodic engine:**
   ```bash
   curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic \
     -H "Content-Type: application/json" \
     -d '{
       "text": "<user_provided_text>",
       "voice": "aria",
       "format": "wav",
       "prosody": {
         "rate": 1.0,
         "pitch": 0,
         "emphasis": "moderate"
       }
     }'
   ```

   Returns audio data or a presigned URL to the generated audio file.

3. **Alternative: Direct TTS Studio API (if Flute-Gateway is down):**
   ```bash
   curl -sf http://localhost:7861/gradio_api/info | jq .named_endpoints
   ```

   Use the Gradio API endpoints for direct engine access.

4. **Report results to user:**
   - Synthesis status (success/failure)
   - Audio file location or download URL
   - Voice engine used
   - Duration and format details

## Authentication

If `FLUTE_API_KEY` is configured, include it:
```bash
-H "X-API-Key: $FLUTE_API_KEY"
```

## Notes

- Flute-Gateway: port 8055 (HTTP **and** WebSocket — `/v1/voice/stream/tts`, `/v1/voice/agent`)
- Ultimate-TTS-Studio: port 7861 (Gradio UI with 7 engines)
- Available voices depend on loaded TTS engines
- WebSocket streaming recommended for real-time applications
- See `.claude/context/flute-gateway.md` for full API reference
- See `.claude/context/voice-personas.md` for persona configurations
