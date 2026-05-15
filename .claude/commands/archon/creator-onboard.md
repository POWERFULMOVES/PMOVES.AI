---
description: Onboard a new human creator into Archon — provision identity, assign default room, emit archon.mint.creator.v1.
---

Provision a new human creator identity in the PMOVES ecosystem. The third leg of the Archon mint trio (agents, skills, creators).

## Usage

Invoke when the operator says "onboard a creator", "add a new persona", or "register a human collaborator". Captures identity, assigns a default room, and stages the NATS mint event.

## Implementation

### Step 0 — Authenticate via Google OAuth (Supabase)

**Mandatory and primary.** Unlike agent/skill minting (which uses an *existing* creator's session), creator onboarding **provisions** the creator from a fresh Google OAuth handshake. This is the canonical identity-creation path.

1. Direct the new human to sign in:
   - **Prod**: `https://archon.pmoves.ai/auth/sign-up?provider=google`
   - **Dev**: `http://127.0.0.1:3737/auth/sign-up?provider=google`
2. Supabase Auth redirects to Google, returns to `https://supabase.pmoves.ai/auth/v1/callback`, then back to the Archon UI with a session.
3. The Supabase row in `auth.users` is the canonical identity. Capture from the session JWT:
   - `auth.users.id` (UUID) → becomes the `creator_id` in `archon_minted_artifacts`
   - `email` (Google-verified) → used to derive `email_hash`
   - `user_metadata.full_name`, `user_metadata.avatar_url` → optional profile fields
   - `app_metadata.provider` MUST equal `'google'`
4. **No magic-link, no email/password, no SSO with other providers.** Google OAuth is the only enabled provider per `.claude/context/self-hosted-defaults.md` § "Authentication — Google OAuth via Supabase".
5. If the operator running this command is **not the new creator**, the new creator must complete the OAuth handshake themselves (the operator cannot impersonate them). Wait for the operator to relay `auth.users.id` and verified `email` before continuing.

If `supabase.pmoves.ai` is unreachable: halt and surface the wiring docs. Onboarding without OAuth is not supported.

### Step 1 — Collect creator profile (post-auth)

`handle`, `default-room`, and optional fields below are collected AFTER the OAuth handshake confirms identity. `email` is sourced from the verified Google JWT — do not ask the operator to type it.

Ask for:

- `handle` — unique human-readable handle (e.g. `cataclysm`, `phi-knuckles`).
- `role` — one of `delivery`, `control`, `memory`, `creator`, `observer`, or a free-form role.
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
  "creator_id": "<supabase auth.users.id from Step 0>",
  "handle": "<handle>",
  "role": "<role>",
  "email_hash": "<sha256(verified-google-email)>",
  "provider": "google",
  "default_room": "<default-room>",
  "github_username": "<optional>",
  "tailscale_node": "<optional>",
  "minted_at": "<RFC3339>"
}
```

Supabase RLS (Wave 1): only the row's own `creator_id` (the authenticated user) can read/write it; admins (role = 'admin' in `app_metadata`) can read all rows.

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
    "creator_id": "<supabase auth.users.id>",
    "handle": "<handle>",
    "role": "<role>",
    "email_hash": "<sha256>",
    "provider": "google",
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
