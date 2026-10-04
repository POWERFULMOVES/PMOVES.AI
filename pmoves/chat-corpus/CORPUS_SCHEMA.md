# Corpus Schema

One JSONL file per chat: `<alias>/<chat-id>.jsonl`, one record per message.

| Field | Type | Notes |
|---|---|---|
| `chat` | string | chat id (opaque, not an instance identifier) |
| `title` | string | redacted chat title |
| `msg` | int | 1-based message sequence |
| `text` | string | fully redacted raw message (tool-call JSON preserved as text) |

Redaction classes applied (see `pmoves/tools/a0/scrub_chats.py`): JWTs, GitHub/
sk-style keys, `NAME=value` and JSON key/secret assignments, Bearer tokens, LAN
IPs, emails, user paths, instance/container identifiers, known-burned literals.

A release ships with `manifest.json` (from `manifest.template.json`) listing
per-chat message counts, redaction totals, and the scrubber version.
