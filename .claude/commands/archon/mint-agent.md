---
description: Mint a new PMOVES agent through Archon's factory — scaffold persona doc, register form, assign room, emit NATS mint event.
---

Mint a new PMOVES agent through Archon's factory pipeline. End-to-end flow: collect manifest → call Archon factory → QA-gate via subagent → scaffold persona doc + agent definition → publish NATS mint event → confirm.

## Usage

Invoke when the operator says "mint an agent", "create an Archon agent", or "spin up a new persona". This command coordinates the **scaffold → QA → register → publish** ritual. Wave-1 dependency: the `archon:create-agent` MCP tool (W2.2 in the gap-fill roadmap) is not yet implemented — until then, this command emits the payload contract and stages files locally.

## Implementation

Execute the following steps in order. Stop and surface any failure before continuing.

### Step 0 — Authenticate the creator (Google OAuth via Supabase)

**Mandatory.** Minted agents are tied to a creator identity. Confirm an authenticated Supabase session before scaffolding anything.

Probe order:
1. Read `pmoves/configs/env/.env` for `SUPABASE_URL` (should resolve to `https://supabase.pmoves.ai` in prod, `http://127.0.0.1:8000` in dev).
2. Look for an existing creator session token in env (`SUPABASE_ACCESS_TOKEN`) or in `pmoves/ui/.next/cache/auth-session.json` (Next.js SSR cookie cache; dev-only convenience).
3. If no session, instruct the operator to sign in:
   - Prod: open `https://archon.pmoves.ai/auth/sign-in?provider=google`
   - Dev: `curl -X POST "$SUPABASE_URL/auth/v1/authorize?provider=google&redirect_to=http://127.0.0.1:3737/auth/callback"` and follow the returned URL.
4. Verify the resulting JWT contains `provider: 'google'` and `email_verified: true`. Reject if either is missing.
5. Look up the Supabase `auth.users.id` for the JWT's `sub` claim — this becomes `creator_id` in the manifest. Until the Wave-1 `archon_minted_artifacts` table exists, persist `creator_id` to `/tmp/mint-creator-${USER}.json` and reference it in step 4's persona doc frontmatter.

If OAuth wiring is not yet live on this node (`SUPABASE_URL` unreachable), halt with: "Cannot mint without an authenticated creator — Google OAuth via Supabase is mandatory. Configure Supabase Auth at supabase.pmoves.ai and retry." See `.claude/context/self-hosted-defaults.md` § "Authentication — Google OAuth via Supabase" for the canonical wiring.

### Step 1 — Collect the manifest (interactive)

Ask the operator for:

- `agent-name` — kebab-case, unique under `PMOVES-agents.md/` (e.g. `geometry-curator`).
- `role` — short capability summary (e.g. "Validates CHIT-CGP geometry payloads before publish").
- `room` — one of the entries in `pmoves/config/rooms/catalog.json` (`4090-field.room.control`, `5090-voice.room.studio`, `5090-kilocode.room.studio`, `z890-infra.room.fabric`).
- `owning-persona` — the human or higher-tier agent accountable. Default to the authenticated creator's Google email from Step 0; only override if a higher-tier agent (e.g. `delivery-agent`) is the actual owner.
- `coding-agent?` — boolean. If true, also scaffold a `.claude/agents/<agent-name>.md` definition.
- Optional: `tools`, `forms`, `tags`.

Validate the room exists:

```bash
jq -e --arg r "<room>" '.rooms[] | select(.room_id==$r)' pmoves/config/rooms/catalog.json
```

If the room is missing, stop and ask the operator to pick a valid room.

### Step 2 — Call the Archon factory (to-be-built MCP tool)

Contract for the future `archon:create-agent` MCP tool:

```jsonc
{
  "name": "create-agent",
  "input": {
    "agent_name": "<agent-name>",
    "role": "<role>",
    "room_id": "<room>",
    "owning_persona": "<owning-persona>",
    "creator_id": "<supabase auth.users.id from Step 0>",
    "tools": ["<tool>", "..."],
    "tags": ["<tag>", "..."]
  },
  "output": {
    "agent_id": "<uuid>",
    "manifest_url": "https://archon.pmoves.ai/<id>",
    "form_id": "<uuid|null>"
  }
}
```

Supabase RLS policy enforces that `creator_id` matches the authenticated JWT subject; calls without a valid session are rejected at the database layer (Wave 1 schema).

Until the MCP tool ships (W2.2), call Archon's REST API directly **if** `curl -sf http://localhost:8091/healthz | jq -r .status` returns `ok`:

```bash
curl -sf -X POST http://localhost:8091/api/agents \
  -H "content-type: application/json" \
  -d @/tmp/agent-manifest.json | tee /tmp/agent-created.json
```

If the REST endpoint also 404s, persist `/tmp/agent-manifest.json` and tell the operator the API is a Wave-2 dependency — continue with local scaffolding.

### Step 3 — QA-gate via subagent

Dispatch `archon-qa-agent` (`.claude/agents/archon-qa-agent.md`, scaffolded under gap-fill Task 7) with the manifest as input. Block on PASS. If FAIL, surface the QA findings verbatim and stop.

### Step 4 — Scaffold persona doc

Write `PMOVES-agents.md/<agent-name>.md` using this template:

```markdown
---
name: <agent-name>
role: <role>
room: <room>
owning_persona: <owning-persona>
creator_id: <supabase auth.users.id from Step 0>
creator_email: <google email from JWT>
minted_at: <YYYY-MM-DD>
status: provisional
---

# <Agent-Name>

## Mandate

<role>

## Room

Operates in `<room>` (see `pmoves/config/rooms/catalog.json`).

## Tools & Forms

- Tools: <comma-separated or "none">
- Forms: <form_id or "none">

## Mint trail

- Archon agent_id: <uuid>
- Manifest: <archon manifest URL>
- NATS mint event: `archon.mint.agent.v1` (see Step 6)
```

### Step 5 — Scaffold coding-agent definition (conditional)

If `coding-agent?` is true, also write `.claude/agents/<agent-name>.md` mirroring the format of existing agents (`.claude/agents/delivery-agent.md`, `nats-subject-auditor.md`).

### Step 6 — Publish NATS mint event

Stage payload for `archon.mint.agent.v1`:

```jsonc
{
  "subject": "archon.mint.agent.v1",
  "payload": {
    "agent_id": "<uuid>",
    "agent_name": "<agent-name>",
    "room_id": "<room>",
    "owning_persona": "<owning-persona>",
    "manifest_url": "<archon manifest URL>",
    "ts": "<RFC3339>"
  }
}
```

If `pmoves-nats-mcp` is configured in `.claude/mcp.json`, call its `nats_publish` tool. Otherwise, print the payload and the equivalent CLI:

```bash
nats pub archon.mint.agent.v1 "$(cat /tmp/mint-payload.json)"
```

Document the manual fallback so the operator can publish from a node with NATS CLI.

### Step 7 — Await confirmation, then emit `archon.mint.confirmed.v1`

After the operator confirms the agent is live (file exists, room ack'd, downstream consumers happy), emit:

```jsonc
{ "subject": "archon.mint.confirmed.v1", "payload": { "agent_id": "<uuid>", "confirmed_at": "<RFC3339>" } }
```

## Notes

- This command is the canonical mint ritual referenced in the gap-fill roadmap Wave 0 Task 9.
- Wave-1 dependency: Supabase `archon_minted_artifacts` table (W1.10) — the persona doc + NATS event become the audit trail until that table exists.
- Wave-2 dependency: live `archon.mint.*` subjects on the bus (W2.1) and the `archon:create-agent` MCP tool (W2.2).
- Cross-reference: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (claim register) and `pmoves/docs/AGENTS/AGNOTE4482.md` (audit gateway).
