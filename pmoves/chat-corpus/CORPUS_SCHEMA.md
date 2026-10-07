# Corpus Schema

One JSONL file per chat: `<alias>/<chat-id>.jsonl`, one record per message.

| Field | Type | Notes |
|---|---|---|
| `chat` | string | chat id (opaque, not an instance identifier) |
| `title` | string | redacted chat title |
| `msg` | int | 1-based message sequence |
| `text` | string | fully redacted raw message (tool-call JSON preserved as text) |

Redaction classes applied (see `pmoves/tools/a0/scrub_chats.py`): the adapter
redacts ONLY gitleaks-detected Secret strings (JWTs, key/token assignments,
Bearer tokens, LAN IPs, DB-URL passwords, GitHub PATs - upstream + pmoves rules
in gitleaks.toml) plus local burn-list literals. Upstream gitleaks has no email
rule; user paths, instance/container identifiers, and OpenAI sk-proj keys are
NOT redacted (sk-proj is a documented miss - see RECALL_SUITE.md).

A release ships with `manifest.json` (from `manifest.template.json`) listing
per-chat message counts, redaction totals, and the scrubber version.
