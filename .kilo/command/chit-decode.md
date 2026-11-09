Decode a CGP packet from the GEOMETRY BUS.

## Arguments

- `$ARGUMENTS` - CGP packet to decode (JSON or file path)

## Implementation

1. Read the CGP packet (from argument, file, or NATS subscription)
2. Verify checksum integrity (SHA-256)
3. Apply CHIT decoding — hierarchical decompression, hyperbolic extraction
4. Extract payload:
   ```json
   {
     "version": "chit.cgp.v1.0",
     "source": { "agent": "...", "node": "...", "signature": "..." },
     "payload": { "content": "...", "hyperbolic_coords": {}, "spectral_signature": [] }
   }
   ```
5. Verify source agent signature if present
6. Output decoded content

## NATS Subscription (Alternative)

Subscribe to `geometry.packet.decoded.v1` to auto-decode incoming packets:

```python
import asyncio, nats, json

async def handler(msg):
    packet = json.loads(msg.data)
    # Decode and process
    print(f"Decoded from {packet['source']['agent']}")

async def main():
    nc = await nats.connect("nats://nats:pmoves@nats:4222")
    await nc.subscribe("geometry.packet.decoded.v1", cb=handler)
    await asyncio.Future()  # run forever
```

## Related

- `/chit-encode` — Encode CGP packets
- `/chit-bus` — Publish to GEOMETRY BUS
- `/chit-sign` — Sign Graphiti trail entry
- AGNOTE4482.BEATS.md — BPM math reference
