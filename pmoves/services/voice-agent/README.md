# Voice Agent - Multi-Platform Voice Interactions

Unified voice agents for Discord, Telegram, and WhatsApp using n8n workflows integrated with PMOVES.AI infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│            Platform-Specific Triggers                    │
├─────────────────────────────────────────────────────────┤
│  Discord       │  Telegram        │  WhatsApp           │
│  (Community)   │  (Native n8n)    │  (Business API)     │
└──────────┬─────────────┬──────────────────┬─────────────┘
           └─────────────┼──────────────────┘
                         ↓
              ┌──────────────────┐
              │  Platform Router  │
              │  (Normalizer)     │
              └────────┬─────────┘
                       ↓
              ┌──────────────────┐
              │  Voice Pipeline   │
              │  STT → LLM → TTS  │
              └────────┬─────────┘
                       ↓
              ┌──────────────────┐
              │  Response Router  │
              │  (Per Platform)   │
              └──────────────────┘
```

## Technology Stack

| Component | Service | Port |
|-----------|---------|------|
| **STT** | OpenAI Whisper via TensorZero | 3030 |
| **LLM** | Claude/GPT via TensorZero | 3030 |
| **TTS** | ElevenLabs / OpenAI TTS | n8n node |
| **RAG** | Hi-RAG v2 Gateway | 8086 |
| **Storage** | Supabase (PostgreSQL) | 3010 |
| **Events** | NATS JetStream | 4222 |
| **Workflows** | n8n | 5678 |

## Platform Support

### Telegram (Native Support)
- **Trigger:** n8n Telegram Trigger node
- **Voice:** Native voice message support
- **Setup:** Create bot via @BotFather

### WhatsApp (Business API)
- **Trigger:** n8n WhatsApp Business Cloud Trigger
- **Voice:** Voice messages via Business API
- **Setup:** Meta Business API or Twilio

### Discord (Community Node)
- **Trigger:** n8n-nodes-discord-bot
- **Voice:** Voice messages and channel audio
- **Setup:** Discord Developer Portal + community node

## NATS Event Subjects

```yaml
# Voice message received from any platform
voice.message.received.v1:
  platform: "discord" | "telegram" | "whatsapp"
  user_id: string
  message_id: string
  audio_url: string
  timestamp: ISO8601

# Transcription completed
voice.transcription.completed.v1:
  message_id: string
  transcript: string
  language: string
  confidence: float

# Agent response generated
voice.agent.response.v1:
  message_id: string
  response_text: string
  response_audio_url: string (optional)
  model_used: string
```

## n8n Workflows

| Workflow | Description |
|----------|-------------|
| `telegram-voice-agent.json` | Telegram voice bot |
| `whatsapp-voice-agent.json` | WhatsApp voice bot |
| `discord-voice-agent.json` | Discord voice bot |
| `voice-platform-router.json` | Unified platform normalizer |
| `voice-shared-functions.json` | Reusable STT/TTS/RAG nodes |

## Setup

### 1. Database Migration

```bash
# Apply Supabase migration
psql $SUPABASE_URL -f pmoves/migrations/voice_messages.sql
```

### 2. n8n Credentials

Configure in n8n:
- **Telegram:** Bot token from @BotFather
- **WhatsApp:** Business API access token
- **Discord:** Bot token from Developer Portal
- **OpenAI:** API key for Whisper
- **ElevenLabs:** API key for TTS

### 3. Import Workflows

```bash
# Import all voice agent workflows
n8n import:workflow --input=pmoves/n8n-workflows/telegram-voice-agent.json
n8n import:workflow --input=pmoves/n8n-workflows/whatsapp-voice-agent.json
n8n import:workflow --input=pmoves/n8n-workflows/discord-voice-agent.json
```

### 4. Discord Community Node

```bash
# Install in n8n container
cd /usr/local/lib/node_modules/n8n
npm install n8n-nodes-discord-bot
```

## API Integration

### TensorZero Gateway (STT + LLM)

```bash
# Whisper Transcription
curl -X POST http://localhost:3030/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "model=whisper-1"

# LLM Chat
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5",
    "messages": [
      {"role": "system", "content": "You are a helpful voice assistant."},
      {"role": "user", "content": "transcribed text here"}
    ]
  }'
```

### Hi-RAG v2 (Knowledge Retrieval)

```bash
curl -X POST http://localhost:8086/hirag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user question",
    "top_k": 5,
    "rerank": true
  }'
```

## Cost Estimates

| Service | Cost | Volume |
|---------|------|--------|
| OpenAI Whisper | $0.006/min | ~$6/1000 min |
| GPT-4o-mini | $0.15/1M tokens | ~$1.50/10k msgs |
| Claude Sonnet | $3/1M input | ~$3/10k msgs |
| ElevenLabs | $5/mo starter | 30k chars/mo |
| **Total MVP** | ~$15-30/mo | Low volume |

## Monitoring

- **Metrics:** Prometheus at `localhost:9090`
- **Logs:** Loki at `localhost:3100`
- **Dashboards:** Grafana at `localhost:3000`
- **API Metrics:** TensorZero ClickHouse at `localhost:8123`

## Files

```
pmoves/
├── services/voice-agent/
│   └── README.md              # This file
├── migrations/
│   └── voice_messages.sql     # Database schema
└── n8n-workflows/
    ├── telegram-voice-agent.json
    ├── whatsapp-voice-agent.json
    ├── discord-voice-agent.json
    ├── voice-platform-router.json
    └── voice-shared-functions.json
```
