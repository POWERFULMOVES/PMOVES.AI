Check the status of TTS services.

## Usage

Use this command to verify TTS service health and availability.

## Implementation

1. Check Ultimate-TTS-Studio:
```bash
curl -sf http://localhost:7861/gradio_api/info && echo "Ultimate-TTS: OK" || echo "Ultimate-TTS: DOWN"
```

2. Check flute-gateway TTS endpoints:
```bash
curl -sf http://localhost:8055/healthz && echo "Flute-Gateway: OK" || echo "Flute-Gateway: DOWN"
```

3. Check all TTS-related containers:
```bash
docker ps --filter "name=tts" --filter "name=flute" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

4. Check GPU availability for TTS:
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader
```

## Expected Output

```
Ultimate-TTS: OK
Flute-Gateway: OK

CONTAINER              STATUS         PORTS
ultimate-tts-studio    Up 5 mins      0.0.0.0:7861->7861/tcp
flute-gateway          Up 10 mins     0.0.0.0:8055-8056->8055-8056/tcp
```

## Notes

- Ultimate-TTS-Studio runs on port 7861
- Flute-gateway runs on ports 8055 (HTTP) and 8056 (WebSocket)
- GPU is optional but recommended for fast synthesis
