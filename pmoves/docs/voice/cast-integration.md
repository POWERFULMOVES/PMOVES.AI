# Google Cast Integration for PMOVES Voice Agents

Complete guide for integrating Google Cast/Google Home devices with PMOVES.AI voice agents.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [MCP Tools Reference](#mcp-tools-reference)
5. [Cast TTS Gateway API](#cast-tts-gateway-api)
6. [NATS Event Integration](#nats-event-integration)
7. [Voice Agent Pipeline](#voice-agent-pipeline)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)
10. [Performance Tuning](#performance-tuning)

---

## Overview

The PMOVES Cast Integration enables voice agents to output speech to Google Cast devices:

- **Google Nest Audio** (2x)
- **Google Nest Mini**
- **Chromecast** (all generations)
- **Android TV / Google TV**
- **TCL Smart TV**

### Why Local Control?

✅ **No Google authentication** — Works without Google cloud
✅ **No internet dependency** — Fully offline capable
✅ **Direct device control** — Lower latency
✅ **Privacy-preserving** — No cloud data transmission

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES Voice Agent Stack                     │
├─────────────────────────────────────────────────────────────────┤
│ Level 4: Agent Zero [Port 8080]                                │
│ ├── Voice agent orchestration                                   │
│ ├── MCP Bridge with Cast tools                                 │
│ └── Response publishing to NATS                                │
├─────────────────────────────────────────────────────────────────┤
│ Level 3: Flute-Gateway [Port 8055]                             │
│ ├── Prosodic TTS synthesis (91% faster TTFS)                   │
│ ├── Multi-engine routing (VibeVoice, Ultimate-TTS)             │
│ └── WebSocket streaming for real-time audio                     │
├─────────────────────────────────────────────────────────────────┤
│ Level 2: Cast TTS Gateway [Port 8060]                          │
│ ├── Device discovery and caching                                │
│ ├── Audio casting via catt                                      │
│ ├── NATS event publishing                                       │
│ └── Health & metrics monitoring                                 │
├─────────────────────────────────────────────────────────────────┤
│ Level 1: Google Cast Devices                                   │
│ ├── Brysons Speakers speaker (Nest Audio @ 192.168.1.108)     │
│ ├── Brysons Speakers speaker 2 (Nest Audio @ 192.168.1.14)    │
│ ├── Den speaker (Nest Mini @ 192.168.1.181)                   │
│ └── 75QM850G (TCL TV @ 192.168.1.99)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Port | Purpose |
|-----------|------|---------|
| Agent Zero | 8080 | Voice agent orchestration, MCP API |
| Flute-Gateway | 8055 | Prosodic TTS synthesis |
| Cast TTS Gateway | 8060 | Device management, audio casting |
| Ultimate-TTS Studio | 7861 | TTS fallback (7 engines) |
| NATS | 4222 | Event coordination bus |

---

## Quick Start

### Prerequisites

```bash
# Install catt (Cast All The Things)
uv pip install catt

# Verify installation
catt scan
```

### 1. Deploy Cast TTS Gateway

```bash
cd pmoves/services/cast-tts-gateway
docker compose up -d
```

### 2. Discover Devices

```bash
curl -X POST http://localhost:8060/cast/discover
```

Expected output:
```json
{
  "devices": [
    {"name": "Brysons Speakers speaker", "ip": "192.168.1.108"},
    {"name": "Brysons Speakers speaker 2", "ip": "192.168.1.14"},
    {"name": "Den speaker", "ip": "192.168.1.181"},
    {"name": "75QM850G", "ip": "192.168.1.99"}
  ],
  "count": 4
}
```

### 3. Cast Speech

```bash
curl -X POST http://localhost:8060/cast/speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from PMOVES voice agent!",
    "device": "Brysons Speakers speaker"
  }'
```

### 4. Stop Playback

```bash
curl -X POST http://localhost:8060/cast/stop \
  -H "Content-Type: application/json" \
  -d '{"device": "Brysons Speakers speaker"}'
```

---

## MCP Tools Reference

The Cast integration provides 6 MCP tools for Agent Zero:

### cast_discover

**Description**: Scan LAN for Google Cast devices

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "force": {
      "type": "boolean",
      "description": "Force rediscovery even if cache is fresh",
      "default": false
    }
  }
}
```

**Usage Example**:
```bash
curl -X POST http://localhost:8080/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "cast_discover",
    "arguments": {"force": true}
  }'
```

**Returns**:
```
Found 4 Cast device(s):

1. Brysons Speakers speaker
   IP: 192.168.1.108

2. Brysons Speakers speaker 2
   IP: 192.168.1.14

3. Den speaker
   IP: 192.168.1.181

4. 75QM850G
   IP: 192.168.1.99
```

### cast_speech

**Description**: Synthesize TTS and cast to device

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "text": {"type": "string"},
    "device": {"type": "string"},
    "voice": {"type": "string", "default": "Kokoro"},
    "use_flute": {"type": "boolean", "default": true}
  },
  "required": ["text"]
}
```

**Usage Example**:
```bash
curl -X POST http://localhost:8080/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "cast_speech",
    "arguments": {
      "text": "The weather today is sunny with a high of 75 degrees.",
      "device": "Brysons Speakers speaker",
      "voice": "Kokoro"
    }
  }'
```

**Returns**:
```
Casted audio to Brysons Speakers speaker
```

### cast_audio

**Description**: Cast audio file to device

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "audio_path": {"type": "string"},
    "device": {"type": "string"}
  },
  "required": ["audio_path"]
}
```

### cast_status

**Description**: Get device playback status

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "device": {"type": "string"}
  }
}
```

### cast_stop

**Description**: Stop playback on device

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "device": {"type": "string"}
  }
}
```

### cast_list

**Description**: List discovered Cast devices

**Input Schema**: Empty

---

## Cast TTS Gateway API

### Base URL
```
http://localhost:8060
```

### Endpoints

#### GET /healthz

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-13T12:00:00Z",
  "flute_gateway": "healthy",
  "devices_discovered": 4
}
```

#### GET /devices

List all discovered devices.

**Response**:
```json
{
  "devices": [
    {
      "name": "Brysons Speakers speaker",
      "ip": "192.168.1.108",
      "last_seen": 1700000000.0,
      "online": true
    }
  ],
  "count": 4
}
```

#### POST /cast/discover

Trigger device discovery.

**Request**:
```json
{
  "force": true
}
```

#### POST /cast/speech

Synthesize TTS and cast to device.

**Request**:
```json
{
  "text": "Your message here",
  "device": "Brysons Speakers speaker",
  "voice": "default",
  "use_flute": true
}
```

**Response**:
```json
{
  "success": true,
  "device": "Brysons Speakers speaker",
  "message": "Casted to Brysons Speakers speaker"
}
```

#### POST /cast/audio

Cast audio file to device.

**Request**:
```json
{
  "audio_path": "/path/to/audio.mp3",
  "device": "Brysons Speakers speaker"
}
```

#### POST /cast/stop

Stop playback on device.

**Request**:
```json
{
  "device": "Brysons Speakers speaker"
}
```

#### GET /cast/status?device=...

Get device playback status.

#### GET /metrics

Prometheus metrics endpoint.

**Metrics**:
- `cast_tts_requests_total{method, status}` — Total requests
- `cast_tts_latency_seconds` — Request latency
- `cast_device_discoveries_total` — Device discoveries

---

## NATS Event Integration

### Event Subjects

| Subject | Purpose |
|---------|---------|
| `voice.cast.request.v1` | Request TTS casting |
| `voice.cast.completed.v1` | Cast completed successfully |
| `voice.cast.failed.v1` | Cast failed |
| `device.cast.discovered.v1` | New device discovered |
| `device.cast.status.v1` | Device status update |

### Event: voice.cast.completed.v1

Published when audio is successfully cast.

**Payload**:
```json
{
  "device": "Brysons Speakers speaker",
  "text": "Hello from PMOVES",
  "voice": "default",
  "timestamp": "2026-03-13T12:00:00Z"
}
```

### Voice Agent Response Pattern

```python
import asyncio
import json
import nats

async def voice_follow_agent():
    """Voice agent that casts responses to speakers."""

    nc = await nats.connect("nats://nats:pmoves@nats:4222")

    async def handle_agent_response(msg):
        """Handle agent response from Agent Zero."""
        response = json.loads(msg.data.decode())

        # Extract response text
        text = response.get("message", "")
        device = response.get("cast_device", "Brysons Speakers speaker")

        # Cast to speakers via Cast TTS Gateway
        await nc.publish(
            "voice.cast.request.v1",
            json.dumps({
                "text": text,
                "device": device,
                "use_flute": True,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }).encode()
        )

    # Subscribe to agent responses
    await nc.subscribe("agent.response.v1", cb=handle_agent_response)

    # Keep running
    await asyncio.Event().wait()

asyncio.run(voice_follow_agent())
```

### Multi-Room Audio

```python
async def cast_to_all_rooms(text: str):
    """Cast to all Nest speakers simultaneously."""

    devices = [
        "Brysons Speakers speaker",  # Living Room
        "Brysons Speakers speaker 2",  # Kitchen
        "Den speaker",  # Bedroom
    ]

    tasks = []
    for device in devices:
        task = asyncio.create_task(cast_speech.invoke({
            "text": text,
            "device": device,
        }))
        tasks.append(task)

    await asyncio.gather(*tasks)
```

---

## Voice Agent Pipeline

### Architecture

```
User Input (Text/Voice)
  ↓
Agent Zero (LLM Processing)
  ↓
Response Generation
  ↓
Publish to: agent.response.v1
  ↓
Voice Follow Agent (Subscribes to agent.response.v1)
  ↓
Cast TTS Gateway (TTS Synthesis + Casting)
  ↓
Publish to: voice.cast.completed.v1
  ↓
Open-Notebook (Log conversation)
  ↓
Google Cast Device (Audio Output)
```

### Implementation: Voice Agent with Cast Output

```python
from archon import AgentForm
import nats
import json

class VoiceAgentWithCast(AgentForm):
    """Voice agent that outputs to Cast devices."""

    async def process_response(self, response: str):
        """Process agent response and cast to speakers."""

        # 1. Generate response (via Agent Zero)
        await self.publish_to_nats("agent.response.v1", {
            "message": response,
            "cast_to_speakers": True,
            "cast_device": "Brysons Speakers speaker",
        })

        # 2. Voice follow agent picks up and casts
        # (Handled by separate voice follow agent service)

    async def run(self):
        """Run voice agent loop."""
        nc = await nats.connect(self.nats_url)

        # Subscribe to user input
        async def handle_input(msg):
            user_input = json.loads(msg.data.decode())
            response = await self.generate_response(user_input["text"])
            await self.process_response(response)

        await nc.subscribe("voice.input.v1", cb=handle_input)
        await asyncio.Event().wait()
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8060 | Cast TTS Gateway HTTP port |
| `FLUTE_GATEWAY_URL` | http://localhost:8055 | Flute-Gateway URL |
| `ULTIMATE_TTS_URL` | http://localhost:7861 | Ultimate-TTS URL |
| `NATS_URL` | nats://nats:pmoves@nats:4222 | NATS message bus |
| `CAST_DEFAULT_DEVICE` | — | Default Cast device name |

### Device Discovery

- **Interval**: 300 seconds (5 minutes)
- **Timeout**: 30 seconds
- **Cache**: In-memory, persists across requests

### TTS Providers

| Provider | Engine | TTFS | Fallback |
|----------|--------|------|----------|
| Flute-Gateway | Prosodic | 91% faster | No |
| Ultimate-TTS | Kokoro, F5-TTS, KittenTTS | Baseline | Yes |
| Google TTS | gTTS | Slow | Yes |

---

## Troubleshooting

### No Devices Discovered

**Symptoms**: `cast_discover` returns 0 devices

**Solutions**:
1. **Check network connectivity**:
   ```bash
   ping 192.168.1.108
   ```

2. **Verify mDNS/UDP 5353 is open**:
   ```bash
   sudo ufw allow 5353/udp
   ```

3. **Ensure devices are on same LAN**:
   ```bash
   arp -a | grep -i chromecast
   ```

4. **Test catt manually**:
   ```bash
   catt scan
   ```

### TTS Synthesis Fails

**Symptoms**: `cast_speech` returns "Failed to synthesize TTS"

**Solutions**:
1. **Check Flute-Gateway health**:
   ```bash
   curl http://localhost:8055/healthz
   ```

2. **Check Ultimate-TTS health**:
   ```bash
   curl http://localhost:7861/gradio_api/info
   ```

3. **Test Flute-Gateway directly**:
   ```bash
   curl -X POST http://localhost:8055/v1/voice/synthesize/prosodic \
     -H "Content-Type: application/json" \
     -d '{"text": "Test", "voice": "default"}' \
     --output test.mp3
   ```

### Audio Casting Fails

**Symptoms**: `cast_speech` returns "Cast failed"

**Solutions**:
1. **Verify device is online**:
   ```bash
   catt status -d "Brysons Speakers speaker"
   ```

2. **Check audio file format** (MP3 recommended):
   ```bash
   file test.mp3
   ```

3. **Test catt directly**:
   ```bash
   catt cast test.mp3 -d "Brysons Speakers speaker"
   ```

4. **Ensure device is not in use**:
   ```bash
   catt stop -d "Brysons Speakers speaker"
   ```

### Device Not Responding

**Symptoms**: Device appears in discovery but casting fails

**Solutions**:
1. **Power cycle device** (unplug for 10 seconds)
2. **Check device IP hasn't changed**:
   ```bash
   catt scan
   ```
3. **Verify no other app is using the device**
4. **Check router multicast settings** (enable mDNS)

---

## Performance Tuning

### TTFS (Time To First Speech)

| Method | TTFS | Notes |
|--------|------|-------|
| Flute-Gateway Prosodic | 91% faster | Recommended |
| Ultimate-TTS Kokoro | Baseline | Good quality |
| Ultimate-TTS F5-TTS | Slower | Best quality |
| Google TTS | Slow | Fallback only |

### Concurrent Casts

- **Max concurrent**: 4 devices simultaneously
- **Recommended**: 2 devices for best quality
- **Latency**: < 100ms per device

### Device Discovery

- **Default interval**: 300 seconds (5 minutes)
- **Force discovery**: `force: true` parameter
- **Cache duration**: 300 seconds

### Network Bandwidth

- **Typical MP3 bitrate**: 128 kbps
- **Per device bandwidth**: ~1 MB/min
- **4 devices**: ~4 MB/min

---

## Advanced Usage

### Custom Voice Profiles

```python
# Flute-Gateway custom voice
await cast_speech.invoke({
    "text": "Custom voice test",
    "voice": "pmoves-custom",  # Custom voice profile
    "use_flute": True,
})

# Ultimate-TTS engine selection
await cast_speech.invoke({
    "text": "F5-TTS quality test",
    "voice": "F5-TTS",
    "use_flute": False,
})
```

### Priority Queue

```python
from collections import deque

class CastQueue:
    """Priority queue for casting."""

    def __init__(self):
        self.queue = deque()

    async def enqueue(self, text: str, priority: int = 0):
        """Add to queue with priority."""
        self.queue.append((priority, text))
        self.queue = deque(sorted(self.queue, key=lambda x: -x[0]))

    async def process(self):
        """Process queue."""
        while self.queue:
            priority, text = self.queue.popleft()
            await cast_speech.invoke({"text": text})
```

### Scheduled Announcements

```python
import asyncio
from datetime import datetime, timedelta

async def scheduled_cast(text: str, delay: int):
    """Cast text after delay seconds."""
    await asyncio.sleep(delay)
    await cast_speech.invoke({"text": text})

# Schedule announcement in 10 minutes
asyncio.create_task(scheduled_cast("Meeting starting in 5 minutes", 600))
```

---

## References

- [Flute-Gateway Documentation](../services/flute-gateway/README.md)
- [Ultimate-TTS Studio](../../PMOVES-Ultimate-TTS-Studio-local/README.md)
- [Agent Zero MCP API](../../PMOVES-Agent-Zero/README.md)
- [NATS Message Bus](./nats-subjects.md)
- [Open-Notebook Integration](./notebook-sync.md)

---

## License

MIT

## Support

- GitHub Issues: https://github.com/POWERFULMOVES/PMOVES.AI/issues
- Discord: https://discord.gg/pmoves
- Email: support@pmoves.ai
