# PMOVES Cast TTS Gateway

Central service for TTS synthesis and casting to Google Cast devices.

## Features

- **Device Discovery**: Automatic discovery of Google Cast devices on LAN
- **TTS Synthesis**: Integration with Flute-Gateway (prosodic) and Ultimate-TTS Studio
- **Audio Casting**: Cast audio files to Nest Audio, Nest Mini, Chromecast, Android TV
- **NATS Integration**: Event publishing for voice agent coordination
- **Metrics**: Prometheus metrics for observability

## Architecture

```
Voice Agent → Flute-Gateway → Cast TTS Gateway → Google Cast Devices
     ↓              ↓                  ↓                    ↓
  NATS Events  Prosodic TTS    Device Manager     Nest Speakers/TV
```

## Endpoints

### Health Check
```bash
GET /healthz
```

### Device Discovery
```bash
POST /cast/discover
{
  "force": true  # Force rediscovery
}
```

### List Devices
```bash
GET /devices
```

### Cast Speech (TTS)
```bash
POST /cast/speech
{
  "text": "Hello from PMOVES",
  "device": "Brysons Speakers speaker",  # Optional
  "voice": "default",  # Optional
  "use_flute": true  # Use Flute-Gateway (default) or Ultimate-TTS
}
```

### Cast Audio File
```bash
POST /cast/audio
{
  "audio_path": "/path/to/audio.mp3",
  "device": "Brysons Speakers speaker"  # Optional
}
```

### Stop Playback
```bash
POST /cast/stop
{
  "device": "Brysons Speakers speaker"  # Optional
}
```

### Device Status
```bash
GET /cast/status?device=Brysons Speakers speaker
```

## NATS Events

### voice.cast.completed.v1
Published when audio is successfully cast:
```json
{
  "device": "Brysons Speakers speaker",
  "text": "Hello from PMOVES",
  "voice": "default",
  "timestamp": "2026-03-13T12:00:00Z"
}
```

## Deployment

### Docker Compose
```bash
docker compose -f docker-compose.yml up -d
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8060 | HTTP port |
| `FLUTE_GATEWAY_URL` | http://localhost:8055 | Flute-Gateway URL |
| `ULTIMATE_TTS_URL` | http://localhost:7861 | Ultimate-TTS URL |
| `NATS_URL` | nats://nats:pmoves@nats:4222 | NATS message bus |

## Usage Examples

### via curl
```bash
# Discover devices
curl -X POST http://localhost:8060/cast/discover

# Cast speech
curl -X POST http://localhost:8060/cast/speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from PMOVES voice agent", "device": "Brysons Speakers speaker"}'

# Stop playback
curl -X POST http://localhost:8060/cast/stop \
  -H "Content-Type: application/json" \
  -d '{"device": "Brysons Speakers speaker"}'
```

### via Agent Zero MCP API
```bash
curl -X POST http://localhost:8080/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "cast_speech",
    "arguments": {
      "text": "Hello from Agent Zero",
      "device": "Brysons Speakers speaker"
    }
  }'
```

## Discovered Devices

Currently discovered on LAN:
- **Brysons Speakers speaker** (Nest Audio) @ 192.168.1.108
- **Brysons Speakers speaker 2** (Nest Audio) @ 192.168.1.14
- **Den speaker** (Nest Mini) @ 192.168.1.181
- **75QM850G** (TCL TV) @ 192.168.1.99

## Metrics

Exposed at `/metrics`:
- `cast_tts_requests_total` - Total requests by method and status
- `cast_tts_latency_seconds` - Request latency histogram
- `cast_device_discoveries_total` - Total device discoveries

## Development

### Prerequisites
```bash
# Install catt (Cast All The Things)
pip install catt[all]

# Install Python dependencies
pip install -r requirements.txt
```

### Run Locally
```bash
# Set environment variables
export FLUTE_GATEWAY_URL=http://localhost:8055
export ULTIMATE_TTS_URL=http://localhost:7861
export NATS_URL=nats://nats:pmoves@localhost:4222

# Run service
python service.py
```

## Troubleshooting

### No devices discovered
- Ensure devices are on the same LAN
- Check firewall settings (mDNS/UDP port 5353)
- Verify catt is installed: `catt scan`

### TTS synthesis fails
- Check Flute-Gateway health: `curl http://localhost:8055/healthz`
- Check Ultimate-TTS health: `curl http://localhost:7861/gradio_api/info`

### Audio casting fails
- Verify device is online: `catt status -d "Device Name"`
- Check network connectivity to device IP
- Ensure audio file is accessible

## Integration with Voice Agents

The Cast TTS Gateway integrates with PMOVES voice agents via:

1. **Agent Zero MCP API**: Cast tools registered in MCP Bridge
2. **NATS Events**: Subscribe to `voice.cast.completed.v1`
3. **Flute-Gateway**: Prosodic TTS synthesis (91% faster TTFS)
4. **Open-Notebook**: Log cast events for conversation history

## Security

- Runs as non-root user (uid 65532)
- Read-only filesystem
- All capabilities dropped
- Resource limits: 1 CPU, 512MB RAM
- Health check every 30 seconds
