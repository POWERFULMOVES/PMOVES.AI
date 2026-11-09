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

> **Egress constraint — DARKXSIDE is gated, not direct.** DARKXSIDE is a *private*
> persona. `pmoves/config/rooms/darkxsides.room.json` sets
> `access.visibility: private`, `owner_only: true`, and
> `policies.publish.allow_external_publish: false` with `gate_mode: "manual"`,
> `allowed_subjects: ["content.publish.approved.v1"]`, and an
> `egress_redaction_floor` that is `fail_closed: true` and explicitly "cannot be
> bypassed by opening the gate". `agent_registry.yaml` (`darkxside_persona`)
> agrees: its only publish subject is `content.publish.approved.v1`, and its
> description reads "public egress remains approval- and redaction-gated".
>
> A DARKXSIDE cell in the matrix below therefore denotes an **inbound / gated
> outbound** identity, not a direct publish path. Outbound messages on
> public/client channels (Discord, WhatsApp, Slack, and Signal where the peer is
> not the owner) MUST be emitted on `content.publish.approved.v1` and delivered
> by the approved publisher after the manual gate and the redaction floor. Wiring
> a per-instance channel plugin to post as DARKXSIDE directly bypasses all three
> controls and is out of scope for this plan. Telegram `@DARKXSIDE_BOT` and
> owner-only Signal remain direct because they are owner-private surfaces.

### Core Personas (from agent_signatures.yaml)

| Agent            | Glyph | Telegram        | Discord         | Signal        | WhatsApp      | Slack         | Teams |
|------------------|-------|-----------------|-----------------|---------------|---------------|---------------|-------|
| **KiloClaw** (this) | 🔮   | @PMOVESKiLO_BOT | KiLO-Claw       | (future)      | (future)      | (future)      | —     |
| **DARKXSIDE**    | ✦    | @DARKXSIDE_BOT  | DARKXSIDE 🔒     | DARKXSIDE 🔒   | DARKXSIDE 🔒   | DARKXSIDE-PMOVES 🔒 | — |
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
- 🔒 = **gated egress.** Inbound only, or outbound only via
  `content.publish.approved.v1` through the manual publish gate and the
  fail-closed redaction floor. No direct per-instance channel-plugin publish.

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
2. **DARKXSIDE** — Cocreator witness persona (inbound + gated egress only, see 🔒)
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
- Owner-private peer only. Any non-owner peer makes this a public egress surface:
- 🔒 DARKXSIDE outbound here is **gated**: emit on `content.publish.approved.v1` and let the approved publisher deliver it after the manual gate + fail-closed redaction floor. Do not wire the channel plugin to post as DARKXSIDE directly.
- Store as: `SIGNAL_PHONE_NUMBER`, `SIGNAL_CLI_CONFIG`

### Phase 1D: WhatsApp (After Signal)
- Install wacli or WhatsApp Business API plugin
- Need a phone number (can share with Signal or separate)
- Identity: DARKXSIDE for international reach
- 🔒 DARKXSIDE outbound here is **gated**: emit on `content.publish.approved.v1` and let the approved publisher deliver it after the manual gate + fail-closed redaction floor. Do not wire the channel plugin to post as DARKXSIDE directly.
- Store as: `WHATSAPP_PHONE_NUMBER`, `WHATSAPP_API_TOKEN`

### Phase 1E: Slack (Enterprise)
- Create Slack App at api.slack.com/apps
- Get `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` (socket mode)
- Identities: DARKXSIDE-PMOVES, Claude-PMOVES (for client work)
- 🔒 DARKXSIDE outbound here is **gated**: emit on `content.publish.approved.v1` and let the approved publisher deliver it after the manual gate + fail-closed redaction floor. Do not wire the channel plugin to post as DARKXSIDE directly.
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
5. New secret labels registered **through the CHIT generator, not by hand**:
   - Edit `REGISTRY` in `pmoves/tools/chit_manifest_register.py` (the code-level
     source of truth) to add each new channel token label.
   - `make -C pmoves chit-manifest-register` — idempotently adds the missing
     registry entries to the **v2** manifest.
   - `make -C pmoves chit-manifest-sync` — regenerates the **v1** manifest *from*
     v2 (file/key targets + alias hints).
   - `make -C pmoves secrets-funnel` — projects the labels into the generated
     tier env files.

   The secrets manifests are **machine-emitted**. Hand-adding labels to the
   derived v1 YAML is discarded by the next `chit-manifest-sync` (it syncs v1
   *from* v2), so the funnel would never reliably own or project them.
6. Updated `docs/SECRETS_ONBOARDING.md` — new token names

---

## Open Questions (need your input)

> **Never paste a bot token into chat.** Bot tokens are bearer credentials. A
> token sent to an agent lands in conversation history, transcripts and logs
> outside the approved secret stores, and must then be treated as compromised
> and rotated. The operator creates the bot, puts the token in `env.shared` /
> `.env.local` (or the production CHIT bundle), and runs the funnel — see
> "PR Scope" item 5. The agent only ever sees the *label*, never the value.
> The questions below ask which **bots to create**, never for their tokens.

1. **Telegram:** Want me to walk you through creating each bot via @BotFather, or will you create them yourself? Either way *you* place each token in `env.shared` / `.env.local` under its `TELEGRAM_BOT_TOKEN_*` label and run `make -C pmoves secrets-funnel`. Do not send tokens here.
2. **Discord:** Same question — want the Developer Portal walkthrough, or will you create them yourself? Same handling: token goes into `env.shared` / `.env.local` under its `DISCORD_BOT_TOKEN_*` label, then run the funnel. Do not send tokens here.
3. **Discord server:** Still "Gun Range"? Want a separate server for agent bots?
4. **Signal:** Do you have a phone number to use, or need to get a VoIP one?
5. **WhatsApp:** Same — existing number or new?
6. **Slack:** Existing workspace or create new?
7. **Naming:** Are the bot names above right, or do you want different handles?
