# NATS Monitor

Monitor NATS message flow in real-time for debugging and observability.

## Instructions

Monitor NATS subjects for real-time message flow. The user should provide:
1. **Subject pattern** — NATS subject to monitor (supports wildcards: `>`, `*`)

```bash
# Monitor all messages (use with caution — high volume)
nats sub ">" --count 10
```

```bash
# Monitor specific subject pattern
nats sub "$SUBJECT_PATTERN" --count 20
```

```bash
# Monitor research events
nats sub "research.>" --count 10
```

```bash
# Monitor ingestion pipeline
nats sub "ingest.>" --count 10
```

Common patterns:
- `research.>` — all research events
- `ingest.>` — all ingestion events
- `geometry.>` — all geometry bus events
- `botz.>` — all BoTZ work distribution
- `mesh.>` — mesh node announcements

**Notes:**
- Requires `nats` CLI tool
- Use `--count N` to limit output
- Use `>` for all sub-subjects, `*` for single-level wildcard
