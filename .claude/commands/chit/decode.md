# CHIT Decode

Decode a CGP v2 (CHIT Geometry Packet) received from the GEOMETRY BUS.

## Arguments

- `$ARGUMENTS` - CGP v2 packet (JSON) or NATS message ID

## Instructions

1. Parse the CGP v2 packet
2. Verify checksum integrity
3. Validate spectral signature using Riemann zeta zeros
4. Extract hyperbolic coordinates
5. Decode holographic boundary representation
6. Reconstruct original payload
7. Report:
   - Original content
   - Encoding metadata (curvature, spectral match)
   - Integrity status

## CGP v2 Packet Structure

```json
{
  "version": "cgp.v2",
  "timestamp": "2025-12-22T00:00:00Z",
  "payload": {
    "content": "original data",
    "hyperbolic_coords": {"x": 0.3, "y": -0.2, "curvature": -1},
    "spectral_signature": [14.134725, 21.022040, 25.010858],
    "holographic_boundary": "base64..."
  },
  "checksum": "sha256hash"
}
```

## Example

```bash
# Decode a packet
/chit:decode '{"version": "cgp.v2", ...}'

# Decode from NATS message
/chit:decode nats://geometry.packet.encoded.v1/msg-123
```

## Related

- `/chit:encode` - Encode data as CGP v2
- `/chit:visualize` - Visualize decoded geometry
