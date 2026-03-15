# PMOVES Google Cast Integration

Google Cast/Google Home integration for PMOVES.AI voice agents.

## Features

- **Device Discovery**: Automatic discovery of Google Cast devices on LAN
- **TTS Synthesis**: Prosodic TTS via Flute-Gateway (91% faster TTFS)
- **Multi-Device Support**: Nest Audio, Nest Mini, Chromecast, Android TV
- **NATS Coordination**: Event-driven voice agent responses
- **MCP Tools**: Direct Agent Zero integration

## Supported Devices

- Google Nest Audio
- Google Nest Mini
- Google Home
- Chromecast (1st, 2nd, 3rd Gen, Ultra)
- Chromecast Audio
- Android TV
- Google TV

## Quick Start

### 1. Start Cast TTS Gateway
```bash
cd pmoves/services/cast-tts-gateway
docker compose up -d
```

### 2. Discover Devices
```bash
curl -X POST http://localhost:8060/cast/discover
```

### 3. Cast Speech
```bash
curl -X POST http://localhost:8060/cast/speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from PMOVES voice agent",
    "device": "Brysons Speakers speaker"
  }'
```

## MCP Tools (Agent Zero)

### cast_discover
```json
{
  "tool": "cast_discover",
  "arguments": {
    "force": true
  }
}
```

### cast_speech
```json
{
  "tool": "cast_speech",
  "arguments": {
    "text": "Your message here",
    "device": "Brysons Speakers speaker",
    "voice": "default",
    "use_flute": true
  }
}
```

### cast_list
```json
{
  "tool": "cast_list",
  "arguments": {}
}
```

### cast_stop
```json
{
  "tool": "cast_stop",
  "arguments": {
    "device": "Brysons Speakers speaker"
  }
}
```

## NATS Events

### Voice Agent Response Pattern
```
Agent Zero generates response
  → Publishes to: agent.response.v1
  → Voice follow agent subscribes
  → Calls Cast TTS Gateway
  → Publishes to: voice.cast.completed.v1
  → Logs to Open-Notebook
```

### Event: voice.cast.completed.v1
```json
{
  "device": "Brysons Speakers speaker",
  "text": "Hello from PMOVES",
  "voice": "default",
  "timestamp": "2026-03-13T12:00:00Z"
}
```

## Configuration

### Environment Variables
```bash
export FLUTE_GATEWAY_URL=http://localhost:8055
export ULTIMATE_TTS_URL=http://localhost:7861
export NATS_URL=nats://nats:pmoves@nats:4222
export CAST_DEFAULT_DEVICE="Brysons Speakers speaker"
```

### Discovery Schedule
- Devices are discovered every 5 minutes automatically
- Force rediscovery with `force: true` parameter
- Device cache persists for 300 seconds

## Examples

### Voice Agent with Cast Output
```python
import asyncio
import nats

async def voice_agent_with_cast():
    nc = await nats.connect()

    # Subscribe to voice agent responses
    async def handle_response(msg):
        response = json.loads(msg.data.decode())

        # Cast to speakers
        await nc.publish(
            "voice.cast.request.v1",
            json.dumps({
                "text": response["message"],
                "device": "Brysons Speakers speaker",
                "use_flute": True,
            }).encode()
        )

    await nc.subscribe("agent.response.v1", cb=handle_response)

    # Keep running
    await asyncio.Event().wait()

asyncio.run(voice_agent_with_cast())
```

### Multi-Room Audio
```python
async def cast_to_multiple_rooms():
    devices = [
        "Brysons Speakers speaker",  # Living Room
        "Brysons Speakers speaker 2",  # Kitchen
        "Den speaker",  # Bedroom
    ]

    for device in devices:
        await cast_speech.invoke({
            "text": "Dinner is ready!",
            "device": device,
        })
```

## Troubleshooting

### No devices discovered
- Check network connectivity: `ping 192.168.1.108`
- Verify mDNS/UDP 5353 is open
- Ensure devices are on the same LAN as the gateway

### TTS fails to synthesize
- Check Flute-Gateway health: `curl http://localhost:8055/healthz`
- Check Ultimate-TTS health: `curl http://localhost:7861/gradio_api/info`
- Verify network connectivity to TTS services

### Audio casting fails
- Verify device is online: `catt status -d "Device Name"`
- Check audio file format (MP3 recommended)
- Ensure device is not in use by another app

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES Voice Agent Stack                     │
├─────────────────────────────────────────────────────────────────┤
│ Level 4: Agent Zero [Port 8080]                                │
│ ├── Voice agent orchestration                                   │
│ ├── Cast MCP tools (discover, speech, stop)                    │
│ └── Voice delegation to subordinates                            │
├─────────────────────────────────────────────────────────────────┤
│ Level 3: Flute-Gateway [Port 8055/8056]                        │
│ ├── TTS routing (VibeVoice, Ultimate-TTS)                      │
│ ├── Prosodic synthesis (91% faster TTFS)                        │
│ └── WebSocket streaming                                         │
├─────────────────────────────────────────────────────────────────┤
│ Level 2: Cast TTS Service [Port 8060]                          │
│ ├── Device discovery and management                            │
│ ├── Audio casting to Nest speakers                             │
│ ├── NATS event coordination                                     │
│ └── Device health monitoring                                    │
├─────────────────────────────────────────────────────────────────┤
│ Level 1: Google Cast Devices                                   │
│ ├── Nest Audio x2                                               │
│ ├── Nest Mini                                                   │
│ └── TCL TV                                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Performance

- **TTFS (Time To First Speech)**: 91% faster with Flute-Gateway prosodic
- **Device Discovery**: < 5 seconds on typical LAN
- **Audio Latency**: < 100ms for local casting
- **Concurrent Casts**: Supports up to 4 devices simultaneously

## Security

- Local control only (no Google cloud dependency)
- Uses `catt` library for Cast protocol
- No authentication required for LAN devices
- Read-only filesystem in container
- Non-root user (uid 65532)

## References

- [Flute-Gateway Documentation](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/pmoves/services/flute-gateway)
- [Ultimate-TTS Studio](https://github.com/POWERFULMOVES/PMOVES.AI/tree/main/PMOVES-Ultimate-TTS-Studio-local)
- [catt Library](https://github.com/skorokithakis/catt)
- [Google Cast Protocol](https://developers.google.com/cast)

## License

MIT
