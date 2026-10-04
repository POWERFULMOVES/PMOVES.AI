# PMOVES Chat Corpus (scaffold)

Redacted, operator-curated Agent Zero chat histories published for AI research and
retrieval. **This repository never contains raw chats or live secrets.** Data lands
here only after the full safety pipeline:

1. **Scrub** - `pmoves/tools/a0/scrub-chats.ps1` / `scrub_chats.py` redacts JWTs,
   passwords, API keys, LAN IPs, emails, user paths, and instance identifiers;
   customer-suspect chats are auto-excluded.
2. **Rotate** - every credential that ever appeared in any chat is rotated first,
   so a missed pattern is dead on arrival.
3. **Review** - operator inspects `findings.md` / `findings.csv` before release.
4. **Publish** - only the redacted JSONL directories move into this repo.

## Layout

- `CORPUS_SCHEMA.md` - JSONL record schema
- `manifest.template.json` - per-release manifest (instance alias, date range, counts)
- data directories appear only after operator review (gitignored by default)

## Exclusions

Chats referencing customer engagements are excluded upstream and never enter
staging for publication. Third-party PII (email addresses, usernames from chat
platforms) is redacted at scrub time.

## License

Corpus data: CC-BY-4.0. Scaffold/tooling: Apache-2.0.
