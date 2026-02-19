# NATS Publish

Publish a message to a NATS subject for testing or triggering workflows.

## Instructions

Publish a message to the specified NATS subject. The user should provide:
1. **Subject** — the NATS subject to publish to (e.g., `research.deepresearch.request.v1`)
2. **Payload** — JSON message body

Common subjects (see `.claude/context/nats-subjects.md`):
- `research.deepresearch.request.v1` — trigger deep research
- `supaserch.request.v1` — trigger holographic search
- `ingest.file.added.v1` — simulate file ingestion event

```bash
# Publish message using nats CLI (if available)
nats pub "$SUBJECT" '$PAYLOAD'
```

```bash
# Alternative: publish via curl to NATS HTTP monitoring
# Note: NATS monitoring API is read-only; for publishing, use nats CLI or a service endpoint
echo "Publishing to: $SUBJECT"
echo "Payload: $PAYLOAD"
```

**Safety notes:**
- Always confirm the subject and payload with the user before publishing
- Production subjects trigger real workflows — use with care
- For testing, prefer subjects with `.test.` in the name
