# NATS Streams

List and inspect NATS JetStream streams.

## Instructions

Query JetStream for active streams and their configuration:

```bash
NATS_URL=$(bash .claude/scripts/nats-endpoint.sh)  # derives host AND port; see that file
# List all streams
curl -s $NATS_URL/jsz?streams=1 | python -c "
import sys, json
d = json.load(sys.stdin)
streams = d.get('account_details', [{}])[0].get('stream_detail', [])
if not streams:
    print('No streams configured')
else:
    for s in streams:
        cfg = s.get('config', {})
        state = s.get('state', {})
        print(f'{cfg.get(\"name\",\"?\")} subjects={cfg.get(\"subjects\",[])} msgs={state.get(\"messages\",0)} bytes={state.get(\"bytes\",0)}')
"
```

```bash
NATS_URL=$(bash .claude/scripts/nats-endpoint.sh)  # derives host AND port; see that file
# Stream consumers
curl -s $NATS_URL/jsz?consumers=1 | python -c "
import sys, json
d = json.load(sys.stdin)
streams = d.get('account_details', [{}])[0].get('stream_detail', [])
for s in streams:
    name = s.get('config', {}).get('name', '?')
    consumers = s.get('consumer_detail', [])
    print(f'{name}: {len(consumers)} consumers')
    for c in consumers:
        cn = c.get('config', {}).get('name', '?')
        print(f'  - {cn}')
"
```

Report:
- All configured streams with subjects and message counts
- Consumer details per stream
- Any streams with zero consumers (potential orphans)
