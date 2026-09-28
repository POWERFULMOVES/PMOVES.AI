# Composio + Discord Onboarding Runbook

**Purpose:** give a brand-new PMOVES fork or a freshly-joined operator everything
needed to stand up the Discord 2-way lane for an AGInTZ (an agent harness
identity) through Composio Connect MCP — no tribal knowledge required.

**Provenance:** `plans/HYPERAGINTZ_ORCHESTRATION_SCOPE_2026-09-19.md`
Amendments A.10–A.13 (operator-routed 2026-09-19). First live lane:
PMOVES-KIMI-KNUCKLES-B850 on the knuckles node, bot app `1524575292188922007`.

**Time:** ~15 minutes of clicking + one automated handoff.

---

## What you are building

```
harness (kimi/claude/openclaw/…) ──MCP──▶ Composio Connect (discordbot, 167 tools) ──▶ Discord
                                              ▲                        │
                                     ck_ consumer key          poll lane (LIST_MESSAGES
                                     per AI client             watermark → NATS → Creator)
```

Outbound = MCP tool calls (`DISCORDBOT_CREATE_MESSAGE`). Inbound = a poll lane
(the discordbot toolkit has **zero triggers** — verified 2026-09-19), so no
gateway websocket is needed for v1.

---

## Prerequisites (check before starting)

- [ ] A Composio org + project you administer (ours: org `pmoves_ai`).
- [ ] A Discord application with a bot user (ours:
      `1524575292188922007`). Create one at
      <https://discord.com/developers/applications> if needed — takes 2 minutes.
- [ ] A node with the Composio CLI authenticated
      (`composio login --no-browser` + `composio login --key <uuid> --poll`;
      verify with `composio whoami` → `current_org_name` set).
- [ ] The funnel labels merged (`COMPOSIO_PROJECT_KEY_PMOVES`,
      `COMPOSIO_CONSUMER_KEY_KIMI`, `DISCORD_BOT_TOKEN_KIMI` — PR #3113 family).

---

## STEP 1 — Mint the Composio project key (`ak_…`) — OPERATOR, 2 min

1. Open your project: <https://dashboard.composio.dev/pmoves_ai>
2. **Settings → Project Settings → API Keys → Create API Key**
   (docs: <https://docs.composio.dev/reference/authenticating-to-composio/project-api-key-permissions>).
3. Permissions: scoped keys pick permission AREAS at creation and **cannot be
   changed afterward** (rotation is the only path). Our key administers MCP
   clients (`/api/v3/mcp/clients`) — pick the areas covering client management
   and connected accounts; if the offered areas don't clearly cover MCP client
   admin, create a default full project key and narrow later via rotation.
4. Copy the `ak_…` key.

## STEP 2 — Mint the Discord bot token — OPERATOR, 2 min

1. Open the app's Bot page (exact link, app-specific):
   <https://discord.com/developers/applications/1524575292188922007/bot>
2. **Privileged Gateway Intents → enable MESSAGE CONTENT INTENT** — without it
   the poll lane sees message metadata but no text. (Required for
   `DISCORDBOT_LIST_MESSAGES` content.)
3. Click **Reset Token** → copy the new token (shown once).
4. Add the bot to your guild with this pre-built URL (permissions integer
   117824 = View Channels, Send Messages, Read History, Embed Links, Attach
   Files, Add Reactions — least surface for the v1 lane):
   <https://discord.com/oauth2/authorize?client_id=1524575292188922007&scope=bot&permissions=117824>
   Change the last number only if you know Discord's permission bits.

## STEP 3 — Place the two values — OPERATOR, 1 min

Append to the node's secrets input (`~/.config/pmoves/secrets/local.env`,
mode 600 — **never paste secrets in chat**):

```
COMPOSIO_PROJECT_KEY_PMOVES=ak_…
DISCORD_BOT_TOKEN_KIMI=…
```

## STEP 4 — Hand to the agent — say "done" and stop

From here the harness agent automates (each step verified before the next):

1. `composio dev auth-configs create --toolkit discordbot` with the bot token
   (custom-credentials form) → the bot identity exists on the developer surface.
2. `POST /api/v3/mcp/clients` with the `ak_` key → creates the
   `<agent>-<node>` Connect client (e.g. `kimi-knuckles`) → returns its `ck_`.
3. `DISCORDBOT_TEST_AUTH` via the new client → token validated end-to-end.
4. `DISCORDBOT_GET_MY_APPLICATION` → confirms app `1524575292188922007`.
5. `.kimi/mcp.json` (or the harness's MCP config) gains the client entry with
   an **env placeholder** — `https://connect.composio.dev/mcp` +
   `x-consumer-api-key: ${COMPOSIO_CONSUMER_KEY_<AGENT>}` — never a literal.
6. Fork-secret distribution: `push-gh-secrets.sh --repo POWERFULMOVES/PMOVES-composio`
   (Composio material) / `--repo POWERFULMOVES/PMOVES-ClawZ` (Discord token).
   Parent PMOVES.AI Prod is at the 100/100 ceiling — never route there.
7. Poll lane service (`comms.discord.message.received.v1` on NATS) + round-trip
   demo: send → poll → bus → Creator render.

## Verification checklist (agent-side, evidence-backed)

| Check | Command / signal | Pass |
|---|---|---|
| CLI session | `composio whoami` | `current_org_name` = your org |
| Auth config | `composio dev auth-configs list` | discordbot ENABLED, 1 connection |
| Client | `GET /api/v3/mcp/clients` (ak_ key) | your client listed |
| Token | `DISCORDBOT_TEST_AUTH` | 200, bot username in response |
| MCP attach | harness lists discordbot tools | 167 tools via client |
| Round trip | send → poll → NATS → render | message visible in Creator output |

## Rotation

- **`ck_` leak/regen:** Dashboard → Connect → client → regenerate → update the
  chit label value → `secrets-funnel` → every MCP client config in the same
  motion (regeneration invalidates the old key immediately).
- **Bot token reset:** repeat Step 2 → re-run Step 4.1 (auth config) →
  `TEST_AUTH`. The poll lane resumes on next tick.
- **`ak_` rotation:** new key → update label → re-run client admin; old key
  delete in dashboard.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| MCP calls 401 `invalid consumer key` | ck_ regenerated but a client still holds the old one | update that client's header from the funnel |
| `LIST_MESSAGES` returns metadata, no text | Message Content intent off | Step 2.2 |
| `/api/v3/mcp/clients` 401 with `uak_` | user key, not project key | use `ak_` (Step 1) |
| `unknown harness 'kimi'` from the registry validator | launcher not in `_LAUNCHER_HARNESSES` | add it (see `fix/secret-shape-kimi-identity`, #3109) |
| Funnel warns `missing` on a new label | value not yet in `local.env` | Steps 3→4 |

---

*Written by PMOVES-KIMI-KNUCKLES-B850, 2026-09-19. If you are a future operator
reading this: the lane that taught us these steps is in the claim register
(`AGNOTE4482PHI.t1.md`) and the scope doc named above. Add what you learn back
here — living docs remember because we sign, ACK, and release.*
