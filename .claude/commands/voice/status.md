Check Flute-Gateway and Ultimate-TTS-Studio health status.

This command verifies the health of the voice synthesis pipeline: Flute-Gateway (prosodic synthesis) and Ultimate-TTS-Studio (multi-engine TTS).

## Usage

Run this command to:
- Verify Flute-Gateway is running and healthy
- Check Ultimate-TTS-Studio engine availability
- List loaded TTS engines and available voices
- Diagnose voice pipeline connectivity issues

## Implementation

Execute the following steps:

1. **Check Flute-Gateway health:**
   ```bash
   curl -sf http://localhost:8055/healthz | jq .
   ```

   Should return status, loaded engines, and WebSocket availability.

2. **Check Ultimate-TTS-Studio:**
   ```bash
   curl -sf http://localhost:7861/gradio_api/info | jq .named_endpoints
   ```

   Should return available Gradio API endpoints.

3. **List available engines (if TTS Studio is running):**
   ```bash
   curl -sf http://localhost:7861/gradio_api/info | jq '.named_endpoints | keys'
   ```

   Expected engines: Kokoro, F5-TTS, KittenTTS, VoxCPM, OuteTTS, Dia, XTTS.

4. **Check WebSocket streaming (Flute-Gateway):**
   ```bash
   curl -sf -o /dev/null -w "%{http_code}" http://localhost:8056/
   ```

   Should return `101` (upgrade to WebSocket) or `200`.

5. **Report results to user:**
   - Flute-Gateway status (port 8055)
   - Ultimate-TTS-Studio status (port 7861)
   - Available engines and voices
   - WebSocket streaming availability
   - Any errors or missing engines

## Notes

- Flute-Gateway requires Ultimate-TTS-Studio as TTS backend
- GPU required for most engines (CUDA 12.4)
- Part of the voice pipeline alongside VibeVoice (port 3000)
- WebSocket on port 8056 for real-time audio streaming
- See `.claude/context/flute-gateway.md` for detailed API reference
