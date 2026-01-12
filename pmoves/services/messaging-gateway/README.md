# Messaging Gateway

Unified messaging gateway service for Discord, Telegram, and WhatsApp notifications with interactive buttons.

## Features

- **Multi-platform support**: Discord, Telegram, WhatsApp
- **Interactive buttons**: Approve/reject workflows with callbacks
- **NATS integration**: Auto-forward ingestion events
- **Unified API**: Single endpoint for all platforms

## Architecture

```
NATS Events → Messaging Gateway → Discord/Telegram/WhatsApp
                    ↓
              Button Callbacks → Approval Actions
```

## API Endpoints

### Health Check
```bash
GET /healthz
```

### Send Message (Unified)
```bash
POST /v1/send
Content-Type: application/json

{
  "platforms": ["discord", "telegram"],
  "content": "New content ready for approval",
  "buttons": [
    {"id": "approve_123", "label": "Approve", "style": "primary"},
    {"id": "reject_123", "label": "Reject", "style": "danger"}
  ]
}
```

### Platform Webhooks

**Discord Interactions:**
```bash
POST /webhooks/discord
```

**Telegram Updates:**
```bash
POST /webhooks/telegram
```

## Configuration

### Environment Variables

```bash
# NATS
NATS_URL=nats://nats:4222
MESSAGING_SUBJECTS=ingest.file.added.v1,ingest.transcript.ready.v1

# Telegram
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_ADMIN_CHAT_IDS=<chat_id_1>,<chat_id_2>

# Discord
DISCORD_WEBHOOK_URL=<webhook_url>
DISCORD_APPLICATION_ID=<app_id>
DISCORD_PUBLIC_KEY=<public_key>

# WhatsApp (optional)
WHATSAPP_ACCESS_TOKEN=<access_token>
WHATSAPP_PHONE_NUMBER_ID=<phone_number_id>
```

## Platform Setup

### Discord

1. **Create Discord Application**: https://discord.com/developers/applications
2. **Enable Interactions**:
   - Set Interactions Endpoint URL: `https://your-domain.com/webhooks/discord`
   - Copy Application ID and Public Key
3. **Create Webhook**:
   - Go to channel settings → Integrations → Webhooks
   - Copy webhook URL

### Telegram

1. **Create Bot**: Talk to [@BotFather](https://t.me/BotFather)
   - Send `/newbot`
   - Follow prompts to get bot token
2. **Set Webhook**:
   ```bash
   curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
     -H "Content-Type: application/json" \
     -d '{"url":"https://your-domain.com/webhooks/telegram"}'
   ```
3. **Get Admin Chat ID**:
   - Message your bot
   - Check updates: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Copy `chat.id` from response

### WhatsApp (Optional)

1. **WhatsApp Business Account**: https://business.whatsapp.com/
2. **Cloud API Access**: https://developers.facebook.com/docs/whatsapp/cloud-api
3. **Get Credentials**:
   - Phone Number ID
   - Access Token
   - Set webhook URL

## Docker Compose

Add to `docker-compose.yml`:

```yaml
messaging-gateway:
  build: ./services/messaging-gateway
  restart: unless-stopped
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
    - DISCORD_APPLICATION_ID=${DISCORD_APPLICATION_ID}
    - DISCORD_PUBLIC_KEY=${DISCORD_PUBLIC_KEY}
    - NATS_URL=${NATS_URL}
  ports: ["8101:8101"]
  profiles: ["workers"]
  networks: [api_tier, bus_tier]
```

## Usage Examples

### Send Multi-Platform Notification

```python
import httpx

async def notify_approval_needed(item_id: str, title: str):
    async with httpx.AsyncClient() as client:
        r = await client.post("http://localhost:8101/v1/send", json={
            "platforms": ["discord", "telegram"],
            "content": f"📥 New item ready: {title}",
            "buttons": [
                {"id": f"approve_{item_id}", "label": "✅ Approve", "style": "success"},
                {"id": f"reject_{item_id}", "label": "❌ Reject", "style": "danger"}
            ]
        })
        return r.json()
```

### Telegram Bot Commands

Users can send `/status` to the bot to check service status.

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload --port 8101
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8101/healthz

# Send test message
curl -X POST http://localhost:8101/v1/send \
  -H "Content-Type: application/json" \
  -d '{
    "platforms": ["discord"],
    "content": "Test message"
  }'
```

## Integration with PMOVES

### Auto-Forward NATS Events

The gateway automatically subscribes to configured NATS subjects and forwards events to all configured platforms.

### Approval Workflow

1. **Event Published**: `ingest.file.added.v1`
2. **Gateway Receives**: Auto-forward to Discord/Telegram
3. **User Clicks Button**: "Approve" or "Reject"
4. **Callback Handled**: Parse button ID, call RPC function
5. **Confirmation Sent**: Update message with result

## TODO

- [ ] Implement Supabase RPC calls for approve/reject actions
- [ ] Add WhatsApp Business API integration
- [ ] Add message templates for common events
- [ ] Add rate limiting per platform
- [ ] Add message retry logic
- [ ] Add analytics/metrics tracking

## References

- [Discord Interactions API](https://discord.com/developers/docs/interactions/receiving-and-responding)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
