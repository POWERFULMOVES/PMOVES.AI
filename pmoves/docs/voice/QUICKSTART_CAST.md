# Google Cast Integration — Quick Start

Get PMOVES voice agents speaking through your Google Cast devices in 5 minutes.

---

## Prerequisites

- PMOVES.AI running (Agent Zero, Flute-Gateway, Ultimate-TTS)
- Google Cast device on same LAN (Nest Audio, Chromecast, etc.)
- `catt` installed: `uv pip install catt`

---

## Step 1: Deploy Cast TTS Gateway (1 minute)

```bash
cd pmoves/services/cast-tts-gateway
docker compose up -d
```

**Verify**:
```bash
curl http://localhost:8060/healthz
```

Expected:
```json
{"status": "healthy", "flute_gateway": "healthy", "devices_discovered": 0}
```

---

## Step 2: Discover Devices (30 seconds)

```bash
curl -X POST http://localhost:8060/cast/discover
```

**Expected output**:
```json
{
  "devices": [
    {"name": "Brysons Speakers speaker", "ip": "192.168.1.108"},
    {"name": "Den speaker", "ip": "192.168.1.181"}
  ],
  "count": 2
}
```

---

## Step 3: Test Cast Speech (30 seconds)

```bash
curl -X POST http://localhost:8060/cast/speech \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from PMOVES voice agent!",
    "device": "Brysons Speakers speaker"
  }'
```

**Expected**: Audio plays on your Nest Audio speaker.

---

## Step 4: Use via Agent Zero MCP (1 minute)

```bash
curl -X POST http://localhost:8080/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "cast_speech",
    "arguments": {
      "text": "This is Agent Zero speaking through Nest speakers",
      "device": "Brysons Speakers speaker"
    }
  }'
```

---

## Step 5: Verify NATS Events (30 seconds)

```bash
nats sub "voice.cast.>"
```

Then trigger another cast — you should see:
```json
{
  "device": "Brysons Speakers speaker",
  "text": "Hello from PMOVES",
  "timestamp": "2026-03-13T12:00:00Z"
}
```

---

## Troubleshooting

### No devices discovered?

```bash
# Test catt directly
catt scan

# Check network
ping 192.168.1.108

# Verify mDNS
sudo ufw allow 5353/udp
```

### TTS fails?

```bash
# Check Flute-Gateway
curl http://localhost:8055/healthz

# Test Ultimate-TTS
curl http://localhost:7861/gradio_api/info
```

### Audio doesn't play?

```bash
# Check device status
catt status -d "Brysons Speakers speaker"

# Test catt directly
echo "Test" | catt cast -d "Brysons Speakers speaker"
```

---

## Next Steps

- **Multi-room audio**: Cast to multiple devices simultaneously
- **Voice agents**: Integrate with Agent Zero for voice responses
- **Scheduled announcements**: Time-based audio notifications
- **Custom voices**: Configure different TTS voices per device

See [full documentation](./cast-integration.md) for details.

---

## Architecture Overview

```
Voice Agent → Agent Zero → Cast MCP Tools → Cast TTS Gateway → Flute-Gateway → Nest Speakers
     ↓              ↓              ↓                 ↓                   ↓              ↓
  User Input   Orchestration  Device Discovery  TTS Synthesis    Prosodic TTS    Audio Output
```

---

## Performance

| Metric | Value |
|--------|-------|
| TTFS (Time To First Speech) | 91% faster with Flute-Gateway |
| Device Discovery | < 5 seconds |
| Audio Latency | < 100ms |
| Concurrent Casts | Up to 4 devices |

---

## Security

- ✅ Local control only (no Google cloud)
- ✅ No authentication required
- ✅ Non-root container
- ✅ Read-only filesystem

---

**Need help?** See [troubleshooting](./cast-integration.md#troubleshooting) or [full docs](./cast-integration.md)
