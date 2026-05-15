---
description: Onboard a new human creator into Archon — provision identity, assign default room, emit archon.mint.creator.v1.
---

Provision a new human creator identity in the PMOVES ecosystem. The third leg of the Archon mint trio (agents, skills, creators).

## Usage

Invoke when the operator says "onboard a creator", "add a new persona", or "register a human collaborator". Captures identity, assigns a default room, and stages the NATS mint event.

## Implementation

### Step 1 — Collect creator identity

Ask the operator for:

- `handle` — unique human-readable handle (e.g. `cataclysm`, `phi-knuckles`).
- `role` — one of `delivery`, `control`, `memory`, `creator`, `observer`, or a free-form role.
- `email` — contact address (will be hashed before publish, not stored plain).
- `default-room` — one of the entries in `pmoves/config/rooms/catalog.json`.
- Optional: `github_username`, `tailscale_node`, `bio`.

Validate the room exists:

```bash
jq -e --arg r "<default-room>" '.rooms[] | select(.room_id==$r)' pmoves/config/rooms/catalog.json
```

### Step 2 — Insert Supabase row (Wave-1 dependency)

The canonical creator registry is the Supabase `archon_minted_artifacts` table (`kind = 'creator'`). This schema is **Wave-1** (W1.10 in the gap-fill roadmap) — not yet provisioned.

Until the table exists, stash the row under `/tmp/creator-<handle>.json`:

```jsonc
{
  "kind": "creator",
  "handle": "<handle>",
  "role": "<role>",
  "email_hash": "<sha256(email)>",
  "default_room": "<default-room>",
  "github_username": "<optional>",
  "tailscale_node": "<optional>",
  "minted_at": "<RFC3339>"
}
```

Compute `email_hash`:

```bash
printf '%s' "<email>" | sha256sum | awk '{print $1}'
```

When the table lands, the row is inserted via Archon's REST API or its `create-creator` MCP tool (contract identical to the JSON above).

### Step 3 — Assign default room

Append a binding entry to `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` under the Active Claim Register (or the creator manifest section if one exists):

```markdown
- creator: <handle> | room: <default-room> | role: <role> | minted: <YYYY-MM-DD>
```

This keeps the human-readable trail in sync with the Supabase ledger.

### Step 4 — Publish NATS mint event

Stage `archon.mint.creator.v1`:

```jsonc
{
  "subject": "archon.mint.creator.v1",
  "payload": {
    "handle": "<handle>",
    "role": "<role>",
    "email_hash": "<sha256>",
    "default_room": "<default-room>",
    "github_username": "<optional>",
    "ts": "<RFC3339>"
  }
}
```

Publish via `pmoves-nats-mcp` `nats_publish` if configured; otherwise emit the payload + manual `nats pub archon.mint.creator.v1 ...` fallback.

### Step 5 — Confirm

After the operator verifies the handle is reachable (e.g. the creator can see their assigned room in P7), emit `archon.mint.confirmed.v1` with `{ "kind": "creator", "handle": "<handle>", "confirmed_at": "<RFC3339>" }`.

## Notes

- Wave-0 Task 9 in the gap-fill roadmap.
- **Wave-1 dependency:** Supabase `archon_minted_artifacts` table (W1.10) gates the durable creator registry; until then the JSON stash + AGNOTE entry are the audit trail.
- Wave-2 dependency: `archon.mint.creator.v1` consumer (W2.1) that materializes the row into the registry and notifies P7.
- Email is never published in plain — only `sha256(email)` reaches NATS. Plain email stays in the local stash for operator reference.
- Companion: `/archon:mint-agent`, `/archon:mint-skill`.
