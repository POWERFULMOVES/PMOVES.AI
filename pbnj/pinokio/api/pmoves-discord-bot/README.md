# PMOVES Discord Bot

CATACLYSM STUDIOS INC community playground bot for Discord. Creates and manages the server structure, routes PMOVES.AI services to channels, and handles agent interactions.

## What it does

- **Server Setup**: Creates categories, channels, roles, webhooks from `channel-structure.yaml`
- **Knowledge Search**: `!ask <query>` routes to Hi-RAG v2 for knowledge retrieval
- **Voice Synthesis**: `!voice <text>` synthesizes speech via Flute-Gateway (14 TTS engines)
- **Auto-Role**: Assigns "Student" role to new members on join
- **Webhook Routing**: Generates webhook URLs for Publisher-Discord NATS event wiring

## Usage

### Via Pinokio
1. Click **Install** to install dependencies
2. Set `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` in environment
3. Click **Setup Server** to create channels/roles (idempotent, safe to re-run)
4. Click **Start Bot** to run the bot

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord bot token (from Discord Developer Portal) |
| `DISCORD_GUILD_ID` | Yes | Discord server ID |

### API (via Discord commands)

**JavaScript:**
```js
// Send a message to trigger search
channel.send('!ask What is CHIT?');

// Trigger voice synthesis
channel.send('!voice Hello from PMOVES');
```

**Python:**
```python
import requests
# Use Publisher-Discord REST API to read messages
resp = requests.get('http://localhost:8094/channels/{channel_id}/messages')
```

**Curl:**
```bash
# Check Publisher-Discord health
curl http://localhost:8094/healthz

# Read channel messages via REST
curl http://localhost:8094/channels/{channel_id}/messages?limit=10
```

## Channel Structure

See `app/config/channel-structure.yaml` for the full declarative server layout.

## Architecture

```
Discord Server ← discord.js bot (this app)
       ↕
Publisher-Discord (port 8094) ← NATS events
       ↕
PMOVES Services (Hi-RAG, Flute-Gateway, Agent Zero, etc.)
```
