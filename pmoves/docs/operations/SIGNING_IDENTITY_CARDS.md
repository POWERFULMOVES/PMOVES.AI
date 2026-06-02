# 5×5 Signing Identity Cards

**Companion to:** `pmoves/config/signing_identity_cards.yaml` (the registry)
**Schema:** `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` (see §6 — pending land)
**Plan reference:** `~/.claude/plans/we-need-work-and-partitioned-hearth.md` (Phase 2)

---

## What a card is

Every signed action in PMOVES.AI — every `git commit`, every CHIT trail entry, every PAT/App-token-authenticated call — has two identities behind it:

- **Machine-loadable (ML)**: the cryptographic credential that *the verifier* (CI, branch protection, sigstore, NATS HMAC) checks. SSH fingerprint, OpenSSH allowed-signers entry, GPG key id, GitHub App installation id, CI runner label.
- **Human-readable (H)**: the identity that *the operator* recognizes at a glance and that the trail records for audit. agent_id, glyph, color, voice, role.

A **Signing Identity Card** binds both halves into one record. The trail handshake (`signing_card_id` field on `signature.v1`) lets any audit walk from a CHIT entry → its card → independently verify both halves agree.

## The 5×5 invariant

> *Five-by-five = perfect-signal channel. When the agent emits its card, the operator confirms against their card, CI verifies the ML half, and the trail records both halves — and all four channels agree on one card_id — the signing is 5×5.*

If any channel disagrees the action is rejected (advisory at first; mandatory after the operator's card has its ML half populated — see plan Owner-Decision D).

The four channels:

| Channel | What it checks | Source |
|---|---|---|
| **Agent emit** | "Here is who I am, here is what I'm signing with" | Agent reads `signing_identity_cards.yaml`, looks up its `agent_id`, declares `signing_card_id` in the CHIT trail entry it produces |
| **Operator confirm** | "I recognize this glyph + role + agent_id" | Trail entry renders glyph/color/voice from the card; operator visually confirms before approving |
| **CI verify** | "The signature on this commit matches the ML half of this card" | branch protection runs `git verify-commit` against `allowed_signers`; runner-label gates on `ci_runner_label` for self-hosted lanes |
| **Trail record** | "The card_id is recorded alongside the signature for post-hoc audit" | `signature.v1.signing_card_id` (uuid) stamped by `pmoves/tools/sign_trail.py` |

## How to issue a new card (operator)

```bash
# 1. Generate an SSH signing key on Z890 (if not already present)
ssh-keygen -t ed25519 -C "darkxside@pmoves.ai" -f ~/.ssh/id_pmoves_signing

# 2. Capture the fingerprint (this is the ML.ssh_fingerprint field)
ssh-keygen -lf ~/.ssh/id_pmoves_signing.pub
# Output: 256 SHA256:abcDEF... darkxside@pmoves.ai (ED25519)

# 3. Build the allowed-signers line (this is ML.ssh_allowed_signers_line)
echo "darkxside@pmoves.ai $(cat ~/.ssh/id_pmoves_signing.pub)" >> ~/.config/git/allowed_signers
git config --global gpg.format ssh
git config --global commit.gpgsign true
git config --global gpg.ssh.allowedSignersFile ~/.config/git/allowed_signers
git config --global user.signingkey ~/.ssh/id_pmoves_signing.pub

# 4. Edit pmoves/config/signing_identity_cards.yaml — fill in the operator's
#    ml.ssh_fingerprint and ml.ssh_allowed_signers_line. Bump the rotated_at
#    timestamp. Keep the same card_id.

# 5. Sign and push the card update — the very first signed commit is the
#    operator's own card landing
git commit -S -m "feat(signing): land DARKXSIDE 5x5 identity card"

# 6. Verify
git verify-commit HEAD
make -C pmoves naming-drift-check  # cards parse + drift gate clean
```

## How agents use cards

Every CHIT trail entry written by `pmoves/tools/sign_trail.py` will (after Phase 4 ships):

1. Read `pmoves/config/signing_identity_cards.yaml`
2. Find the active card whose `h.agent_id` matches the calling `--agent-id`
3. Stamp `signing_card_id` on the `signature.v1` payload
4. Emit `agent.graphiti.signed.v1` with the card_id included

If no active card exists for the agent_id, the signing tool emits a stderr warning and (in mandatory mode) refuses to sign. This makes "agent without a card" a visible audit failure, not a silent gap.

## How to rotate

Cards are append-only — never delete. To rotate (e.g., new SSH key after the old one's compromise window):

```yaml
# Old card — flip to active: false, leave issued_at intact
- card_id: "00000000-0000-4000-8000-000000000001"
  issued_at: "2026-04-26T14:06:00Z"
  rotated_at: "2026-07-15T09:30:00Z"
  active: false
  ml: {...old key fingerprint...}
  h: {...darkxside...}

# New card — fresh card_id, supersedes_card_id points at the old one
- card_id: "00000000-0000-4000-8000-000000000099"
  issued_at: "2026-07-15T09:30:00Z"
  active: true
  supersedes_card_id: "00000000-0000-4000-8000-000000000001"
  ml: {...new key fingerprint...}
  h: {...darkxside...}
```

The audit script (Phase 4) follows the `supersedes_card_id` chain to verify there is exactly one active card per `h.agent_id` at any time.

## Card roles

- **operator** — the human running PMOVES.AI. Exactly one card active at a time (DARKXSIDE).
- **agent** — AI contributors (claude-opus, codex, kilocode, gemini, cline, crush, plus node-bound personas like z890-claude / 5090-claude / 4090-claude). One card per agent identity; node-bound personas are separate cards from the underlying base agent because they sign with different node-affinity context.
- **service-account** — non-human, non-agent signers. Currently one: `github-app`. The PMOVES GitHub App. Its private key is the canonical replacement for PAT once §2 of the sitrep clears.
- **runner** — CI runners (ai-lab, kvm4, kvm2, cloudstartup, spark). They don't sign commits — their identity is the `ci_runner_label` they advertise to GitHub Actions, plus the workflow file that scheduled them. They get cards so the trail can attribute "this commit pushed by github-app, but the build that produced its artifact ran on kvm4-runner" when an ML pipeline crosses the line.

## Why both halves matter

A signature with only the ML half is anonymous: the verifier knows the bytes match a key, but a human reading the trail months later has to look up the fingerprint to figure out who acted. Most audits never run that lookup, and "valid signature, unknown party" passes through.

A signature with only the H half is theatrical: a glyph in a trail entry is meaningful to readers but trivially forgeable.

Tying both halves to one `card_id` and recording it on every trail entry is the minimum a future auditor needs to walk back from any signed action to a verifiable identity in one read.

## Schema reference (canonical)

The schema lives at `pmoves/contracts/schemas/identity/signing-card.v1.schema.json` once landed. Until then, the canonical structure is reproduced here:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Signing Identity Card v1",
  "type": "object",
  "required": ["card_id", "ml", "h", "issued_at", "active"],
  "properties": {
    "card_id": { "type": "string", "format": "uuid" },
    "ml": {
      "type": "object",
      "description": "Machine-loadable identity. What the verifier checks.",
      "required": ["primary_method"],
      "properties": {
        "primary_method": { "enum": ["ssh", "gpg", "github-app"] },
        "ssh_fingerprint": { "type": ["string", "null"], "description": "SHA256:... format" },
        "ssh_allowed_signers_line": { "type": ["string", "null"] },
        "gpg_key_id": { "type": ["string", "null"] },
        "github_app_installation_id": { "type": ["integer", "null"] },
        "ci_runner_label": { "type": ["string", "null"] }
      }
    },
    "h": {
      "type": "object",
      "description": "Human-readable identity. What both sides recognize at a glance.",
      "required": ["agent_id", "glyph", "color", "role"],
      "properties": {
        "agent_id": { "type": "string" },
        "display_name": { "type": "string" },
        "glyph": { "type": "string", "maxLength": 2 },
        "color": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
        "voice": { "type": "string" },
        "role": { "enum": ["operator", "agent", "runner", "service-account"] }
      }
    },
    "issued_at": { "type": "string", "format": "date-time" },
    "rotated_at": { "type": ["string", "null"], "format": "date-time" },
    "active": { "type": "boolean" },
    "supersedes_card_id": { "type": ["string", "null"], "format": "uuid" },
    "notes": { "type": "string" }
  },
  "additionalProperties": false
}
```

When the schema file lands at the canonical path, `audit_naming_drift.py` (Phase 4) will validate `signing_identity_cards.yaml` against it on every run and fail the gate on schema drift.

**Interim:** the schema is currently embedded as a Python dict (`SIGNING_CARD_V1_SCHEMA`) at the top of `pmoves/scripts/audit_naming_drift.py` because `pmoves/contracts/schemas/` is read-only via damage-control policy. The audit gate validates cards against that inline copy. When the policy carve-out for new versioned schema files lands, move the dict to a JSON file at the canonical path and switch the audit to `_read_json()` — keep the inline dict as a fallback for environments without `jsonschema` installed.

<!-- GRAPHITI_MARK: CLAUDE-OPUS::SIGNING-CARDS-EXPLAINER::2026-04-26 -->
<!-- GRAPHITI_MARK: Z890-CLAUDE::CREDENTIAL-AUDIT-REVIEW::2026-04-26 -->
