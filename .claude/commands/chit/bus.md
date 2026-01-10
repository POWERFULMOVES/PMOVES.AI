# CHIT Bus

Interact with the GEOMETRY BUS for publishing and subscribing to CHIT packets.

## Arguments

- `$ARGUMENTS` - Command: `pub`, `sub`, `status`, or `list`

## Instructions

### Publish (`pub`)
```bash
/chit:bus pub geometry.packet.v1 '{"content": "..."}'
```
1. Validate packet is CGP v2 compliant
2. Publish to specified NATS subject
3. Report message ID and confirmation

### Subscribe (`sub`)
```bash
/chit:bus sub geometry.packet.v1
```
1. Subscribe to NATS subject
2. Display incoming packets
3. Optionally auto-decode and visualize

### Status (`status`)
```bash
/chit:bus status
```
1. Check NATS connection
2. List active subscriptions
3. Show recent message statistics

### List Subjects (`list`)
```bash
/chit:bus list
```
List all GEOMETRY BUS subjects (see geometry-nats-subjects.md)

## GEOMETRY BUS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `geometry.packet.encoded.v1` | Pub | Encoded CGP v2 packets |
| `geometry.packet.decoded.v1` | Pub | Decoded packet results |
| `geometry.visualization.request.v1` | Pub | Visualization requests |
| `geometry.visualization.ready.v1` | Pub | Visualization complete |
| `tokenism.transform.v1` | Pub/Sub | Token transformations |
| `evoswarm.population.v1` | Pub | EvoSwarm population events |

## Example

```bash
# Publish a packet
/chit:bus pub geometry.packet.encoded.v1 '{"version": "cgp.v2", ...}'

# Subscribe to all geometry events
/chit:bus sub "geometry.>"

# Check bus status
/chit:bus status
```

## Requires

- NATS server running on port 4222
- JetStream enabled for persistence

## Related

- `/chit:encode` - Create packets
- `/chit:decode` - Decode received packets
