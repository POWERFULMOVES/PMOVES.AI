# PR 3/5: feat(hermes-nats): Add NATS bridge config and test scripts

## Type
- [x] feat
## Scope
hermes-nats
## Description
NATS bridge configuration for Elder-Melchor:
- Subject mappings (publish/subscribe)
- Connectivity test scripts (Python + Windows batch)
- Tailscale fallback support

## Files Changed
- `pmoves/config/nats/hermes/elder-melchor-nats.yaml` (NEW)
- `pmoves/config/nats/hermes/test-nats-bridge.py` (NEW)
- `pmoves/config/nats/hermes/test-nats-bridge.bat` (NEW)

## Checklist
- [x] Atomic commit
- [x] Test scripts verified
