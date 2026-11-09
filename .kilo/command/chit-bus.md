Publish a CGP packet to the GEOMETRY BUS via NATS.

## Arguments

- `$ARGUMENTS` - Subject and optional message (e.g., "geometry.cgp.v1 {json payload}")

## Implementation

1. Parse the NATS subject from the first argument
2. Parse or generate the CGP payload
3. If no payload provided, generate from current context using CHIT encoding
4. Publish to NATS:

```bash
# Publish via nats CLI
nats pub <subject> '<json payload>'

# Or via Python
python -c "
import asyncio, nats, json

async def main():
    nc = await nats.connect('nats://nats:pmoves@nats:4222')
    await nc.publish('<subject>', json.dumps(<payload>).encode())
    await nc.close()

asyncio.run(main())
"
```

## GEOMETRY BUS Subjects

| Subject | Purpose |
|---------|---------|
| `geometry.cgp.v1` | CGP packet broadcast |
| `geometry.transform.request.v1` | Transformation request |
| `geometry.pack.created.v1` | Geometry pack ready |
| `tokenism.signal.new.v1` | New signal detected |
| `tokenism.prosodic.bpm.v1` | BPM prosodic bridge |

## Related

- `/chit-encode` — Encode CGP packets
- `/chit-decode` — Decode CGP packets
- `/chit-sign` — Sign Graphiti trail entry
- AGNOTE4482.BEATS.md — BPM math reference
