Check Pipecat multimodal communications status.

## Usage

Use this command to verify Pipecat and flute-gateway health.

## Implementation

1. Check flute-gateway health:
```bash
curl -sf http://localhost:8055/healthz && echo "Flute-Gateway: OK" || echo "Flute-Gateway: DOWN"
```

2. Check the WebSocket route (same port as HTTP — 8055):
```bash
WSKEY='Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=='
curl -s -o /dev/null -w '%{http_code}' -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' -H "$WSKEY" http://localhost:8055/v1/voice/stream/tts
# expect 101 (switching protocols)
```

3. Check the pipeline feature matrix:
```bash
curl -s http://localhost:8055/v1/voice/config | jq '.features, .providers'
```

> [!NOTE]
> flute-gateway serves no `/v1/pipeline/status` and no `/v1/sessions` — it keeps
> no session registry, so there are no "active sessions" to list.
> `/v1/voice/config` (unauthenticated) is the closest real signal; `/metrics`
> carries per-endpoint request counters.

4. Check container logs:
```bash
docker logs --tail 50 pmoves-flute-gateway-1
```

## Pipecat Components

| Component | Port | Purpose |
|-----------|------|---------|
| HTTP API | 8055 | REST endpoints |
| WebSocket | 8055 | `/v1/voice/stream/tts`, `/v1/voice/agent` |
| TTS Backend | 7861 (container) / 7860 (host-native) | Ultimate-TTS-Studio Gradio UI is published on 7861; flute-gateway's `ULTIMATE_TTS_URL` defaults to the host-native UTS on 7860 (`main.py:156`) |

## Expected Output

```
Flute-Gateway: OK
WebSocket: 101
Providers: omnivoice, ultimate_tts, whisper
```

## Notes

- Pipecat provides real-time voice communication
- WebSocket routes share port 8055 with HTTP; 8056 is published by compose but unbound
- See PR #332 for Pipecat integration details
