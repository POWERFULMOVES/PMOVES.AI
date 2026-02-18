# Discord Notify

Send a notification through the Publisher-Discord service.

## Instructions

Trigger a Discord notification. This works by publishing a NATS event that Publisher-Discord is subscribed to.

The user should provide:
1. **Message** — the notification content
2. **Channel** — target Discord channel (if configurable)

```bash
# Publish a notification event via NATS
# Publisher-Discord listens on: ingest.file.added.v1, ingest.transcript.ready.v1, ingest.summary.ready.v1, ingest.chapters.ready.v1
nats pub "ingest.summary.ready.v1" "{\"title\": \"$TITLE\", \"summary\": \"$MESSAGE\", \"source\": \"manual\"}"
```

```bash
# Verify Publisher-Discord received the event
docker logs publisher-discord --tail 5 2>&1
```

**Notes:**
- Publisher-Discord subscribes to specific NATS subjects
- Messages are formatted as Discord embeds
- Rate limiting may apply
