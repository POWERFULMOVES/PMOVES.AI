# PMOVES Channel Matrix — Multi-Agent Communication Plan

_Last updated: 2026-07-13_

## Objective

Catalog and provision every messaging channel × agent persona combination.
Each agent gets its own bot token per channel where applicable.
PR will be opened once tokens are created and config is wired.

---

## Channel Priority Order

| # | Channel   | Status          | Purpose                          | Blocker                        |
|---|-----------|-----------------|----------------------------------|--------------------------------|
| 1 | Telegram  | Plugin ON, SETUP | Primary bot comms               | Need token wiring              |
| 2 | Discord   | Plugin ON, SETUP | Community + agent ops           | Need token wiring + server cfg |
| 3 | Signal    | Not installed   | Private/secure comms            | Need Signal plugin + number    |
| 4 | WhatsApp  | Not installed   | International/personal reach     | Need wacli/whatsapp plugin     |
| 5 | Slack     | Not installed   | Enterprise clients              | Need Slack workspace + app     |
| 6 | MS Teams  | Not installed   | Enterprise clients              | Azure trial account (deferred) |

---

## Agent → Channel Matrix

Each cell = a unique bot token / identity needed.

### Core Personas (from agent_signatures.yaml)

| Agent            | Glyph | Telegram        | Discord         | Signal        | WhatsApp      | Slack         | Teams |
|------------------|-------|-----------------|-----------------|---------------|---------------|---------------|-------|
| **KiloClaw** (this) | 🔮   | @PMOVESKiLO_BOT | KiLO-Claw       | (future)      | (future)      | (future)      | —     |
| **DARKXSIDE**    | ✦    | @DARKXSIDE_BOT  | DARKXSIDE       | DARKXSIDE     | DARKXSIDE     | DARKXSIDE-PMOVES | — |
| **Crush**        | ◇    | @CrushPMOVES    | Crush           | —             | —             | —             | —     |
| **BoTZ Gateway** | ⌂    | @BoTZGateway    | BoTZ-Gateway    | —             | —             | —             | —     |

### Specialist Personas

| Agent            | Glyph | Telegram        | Discord         | Signal | WhatsApp | Slack | Teams |
|------------------|-------|-----------------|-----------------|--------|----------|-------|-------|
| **Claude Opus**  | ◆    | —               | Claude-Opus     | —      | —        | Claude-PMOVES | —  |
| **Codex**        | ■    | —               | Codex           | —      | —        | —     | —     |
| **Gemini**       | ★    | —               | Gemini          | —      | —        | —     | —     |
| **MiniMax**      | ⬡    | —               | MiniMax         | —      | —        | —     | —     |
| **NemoClaw**     | 🐠    | @NemoClawBot    | NemoClaw        | —      | —        | —     | —     |
| **CoderClaw**    | 💻    | —               | CoderClaw       | —      | —        | —     | —     |
| **SparkClaw**    | ⚡    | —               | SparkClaw       | —      | —        | —     | —     |
| **ROCmClaw**     | 🔴    | —               | ROCmClaw        | —      | —        | —     | —     |

### Legend
- ✅ = token exists / will create
- — = not needed for this channel
- (future) = planned but not this phase

---

## Phase Plan

### Phase 1A: Telegram (Now)
**Tokens to create via @BotFather:**

1. **PMOVES_KiLO_BOT** — This KiloClaw instance (primary assistant)
2. **DARKXSIDE_BOT** — DARKXSIDE persona (self-hosted VPS instance)
3. **CrushPMOVES_BOT** — Crush terminal gateway agent
4. **BoTZGateway_BOT** — BoTZ Gateway system agent
5. **NemoClaw_BOT** — Edge GPU agent (Jetson)

Each bot gets its own token from @BotFather.
Store each as a separate GitHub Secret: `TELEGRAM_BOT_TOKEN_KILOCLAW`, `TELEGRAM_BOT_TOKEN_DARKXSIDE`, etc.

### Phase 1B: Discord (Now)
**Bots to create via Discord Developer Portal:**

1. **KiLO-Claw** — Primary assistant (this instance)
2. **DARKXSIDE** — Cocreator witness persona
3. **Crush** — Terminal gateway companion
4. **BoTZ Gateway** — System ops bot
5. **Claude-PMOVES** — Claude Opus agent
6. **Codex-PMOVES** — Codex agent
7. **MiniMax-PMOVES** — MiniMax agent

Each bot needs: application create → bot user → token → invite to server.
Store each as: `DISCORD_BOT_TOKEN_KILOCLAW`, `DISCORD_BOT_TOKEN_DARKXSIDE`, etc.

Existing Discord server: **Gun Range** (from prior session context).

### Phase 1C: Signal (After Telegram + Discord)
- Install OpenClaw Signal plugin (signal-cli based)
- Need a phone number for Signal (can use VoIP number)
- Single identity: DARKXSIDE for private comms
- Store as: `SIGNAL_PHONE_NUMBER`, `SIGNAL_CLI_CONFIG`

### Phase 1D: WhatsApp (After Signal)
- Install wacli or WhatsApp Business API plugin
- Need a phone number (can share with Signal or separate)
- Identity: DARKXSIDE for international reach
- Store as: `WHATSAPP_PHONE_NUMBER`, `WHATSAPP_API_TOKEN`

### Phase 1E: Slack (Enterprise)
- Create Slack App at api.slack.com/apps
- Get `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` (socket mode)
- Identities: DARKXSIDE-PMOVES, Claude-PMOVES (for client work)
- Need workspace to test in (can create free one)

### Phase 1F: MS Teams (Deferred)
- Requires Azure trial account (user action)
- Register Teams bot via Azure Bot Service
- Lowest priority — enterprise client access only

---

## Token Catalog (GitHub Secrets Naming)

### Telegram
| Secret Name                   | Agent         | Status |
|-------------------------------|---------------|--------|
| `TELEGRAM_BOT_TOKEN`          | (legacy KiloClaw) | exists |
| `TELEGRAM_BOT_TOKEN_DARKXSIDE`| DARKXSIDE     | create |
| `TELEGRAM_BOT_TOKEN_CRUSH`    | Crush         | create |
| `TELEGRAM_BOT_TOKEN_BOTZ`     | BoTZ Gateway  | create |
| `TELEGRAM_BOT_TOKEN_NEMOCLAW` | NemoClaw      | create |

### Discord
| Secret Name                    | Agent         | Status |
|--------------------------------|---------------|--------|
| `DISCORD_BOT_TOKEN`            | (legacy)      | exists |
| `DISCORD_BOT_TOKEN_DARKXSIDE`  | DARKXSIDE     | create |
| `DISCORD_BOT_TOKEN_CRUSH`      | Crush         | create |
| `DISCORD_BOT_TOKEN_BOTZ`       | BoTZ Gateway  | create |
| `DISCORD_BOT_TOKEN_CLAUDE`     | Claude Opus   | create |
| `DISCORD_BOT_TOKEN_CODEX`      | Codex         | create |
| `DISCORD_BOT_TOKEN_MINIMAX`    | MiniMax       | create |

### Signal
| Secret Name                    | Agent         | Status |
|--------------------------------|---------------|--------|
| `SIGNAL_PHONE_NUMBER`          | DARKXSIDE     | create |
| `SIGNAL_CLI_CONFIG_PATH`       | config ref    | create |

### WhatsApp
| Secret Name                    | Agent         | Status |
|--------------------------------|---------------|--------|
| `WHATSAPP_PHONE_NUMBER`        | DARKXSIDE     | create |
| `WHATSAPP_API_TOKEN`           | DARKXSIDE     | create |

### Slack
| Secret Name                    | Agent         | Status |
|--------------------------------|---------------|--------|
| `SLACK_BOT_TOKEN`              | DARKXSIDE     | create |
| `SLACK_APP_TOKEN`              | DARKXSIDE     | create |

---

## Config Structure (per-instance OpenClaw config)

Each OpenClaw instance gets its own channel config block:

```json
{
  "plugins": {
    "entries": {
      "telegram": {
        "enabled": true,
        "config": {
          "token": "<this agent's telegram token>",
          "botName": "<this agent's name>"
        }
      },
      "discord": {
        "enabled": true,
        "config": {
          "token": "<this agent's discord token>",
          "allowedChannels": ["..."],
          "allowedServers": ["..."]
        }
      }
    }
  }
}
```

---

## PR Scope

When all tokens are created and configs wired, open a PR to PMOVES.AI with:
1. Updated `pmoves/config/agent_registry.yaml` — channel mappings per agent
2. Updated `pmoves/config/agent_signatures.yaml` — channel handles per persona
3. New file: `pmoves/config/channel_matrix.yaml` — machine-readable matrix
4. Updated `pmoves/docs/comms/CHANNEL_MATRIX_PLAN.md` — this doc
5. Updated `pmoves/chit/secrets_manifest.yaml` — new secret entries
6. Updated `docs/SECRETS_ONBOARDING.md` — new token names

---

## Open Questions (need your input)

1. **Telegram:** Want me to create the bots via BotFather through this instance, or will you create them manually and paste tokens?
2. **Discord:** Same question — should I walk you through creating each bot in the Developer Portal, or do you want to create them and give me the tokens?
3. **Discord server:** Still "Gun Range"? Want a separate server for agent bots?
4. **Signal:** Do you have a phone number to use, or need to get a VoIP one?
5. **WhatsApp:** Same — existing number or new?
6. **Slack:** Existing workspace or create new?
7. **Naming:** Are the bot names above right, or do you want different handles?
