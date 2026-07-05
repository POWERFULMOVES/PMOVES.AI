---
name: pmoves-nats-subject-audit
description: Diff declared NATS subjects in .claude/context/{nats-subjects.md,geometry-nats-subjects.md} against live JetStream consumers; flag orphans. Use when adding NATS publishers/subscribers.
disable-model-invocation: false
user-invocable: false
---

# pmoves-nats-subject-audit

Compares NATS subjects **declared** in the canonical context docs against subjects **observed live** on the JetStream monitoring endpoint. Emit three buckets so a contributor adding a new publisher/subscriber knows whether the subject is:

- `declared-not-live` — orphan: docs claim it, JetStream has never seen it (stale doc OR producer missing)
- `live-not-declared` — unknown: traffic exists but no doc entry (drift, must add to context)
- `declared-and-live` — ok

## When to invoke

- Before merging a PR that adds, renames, or removes a NATS subject
- During a CHIT review sweep (see `/chit:review-sweep`)
- When triaging "events are firing but nothing consumes" symptoms

## How to run

```bash
python3 .claude/skills/pmoves-nats-subject-audit/scripts/audit.py
```

The script:

1. Parses backtick-quoted dotted identifiers from `.claude/context/nats-subjects.md` and `geometry-nats-subjects.md`.
2. Calls `http://127.0.0.1:8222/jsz?streams=true&consumers=true` (NATS monitoring port; matches CATALOG.md when broker is run with `-m 8222`).
3. Builds the live set from stream subjects and consumer filter subjects.
4. Prints three sections; exits 0 always (informational; CI may wrap with `--strict` later).

## Output

```
== declared-not-live (orphans) ==
- archon.mint.creator.v1
- supaserch.cache.expired.v1

== live-not-declared (drift) ==
- chit.review.sweep.adhoc.v1

== declared-and-live (ok) ==
- archon.mint.agent.v1
- chit.signed.v1
...
```

## Citations

- `.claude/context/nats-subjects.md`
- `.claude/context/geometry-nats-subjects.md`
- `.claude/CATALOG.md` § NATS
