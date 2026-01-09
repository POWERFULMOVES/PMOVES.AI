Check Pipecat multimodal communications status.

## Usage

Use this command to verify Pipecat and flute-gateway health.

## Implementation

1. Check flute-gateway health:
```bash
curl -sf http://localhost:8055/healthz && echo "Flute-Gateway: OK" || echo "Flute-Gateway: DOWN"
```

2. Check WebSocket server:
```bash
# Test WebSocket connectivity
curl -sf http://localhost:8056 --max-time 2 && echo "WebSocket: LISTENING" || echo "WebSocket: DOWN"
```

3. Check Pipecat pipeline status:
```bash
curl -s http://localhost:8055/v1/pipeline/status \
  -H "Authorization: Bearer $FLUTE_API_KEY" | jq '.'
```

4. View active sessions:
```bash
curl -s http://localhost:8055/v1/sessions \
  -H "Authorization: Bearer $FLUTE_API_KEY" | jq '.sessions | length'
```

5. Check container logs:
```bash
docker logs --tail 50 pmoves-flute-gateway-1
```

## Pipecat Components

| Component | Port | Purpose |
|-----------|------|---------|
| HTTP API | 8055 | REST endpoints |
| WebSocket | 8056 | Real-time audio streaming |
| TTS Backend | 7861 | Ultimate-TTS-Studio |

## Expected Output

```
Flute-Gateway: OK
WebSocket: LISTENING
Active sessions: 0
Pipeline status: ready
```

## Notes

- Pipecat provides real-time voice communication
- WebSocket port (8056) handles bidirectional audio
- See PR #332 for Pipecat integration details
