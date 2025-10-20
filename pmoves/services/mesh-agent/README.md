# Mesh Agent

Lightweight agent that can publish CHIT geometry events when relaying data between components.

## Geometry Bus (CHIT) Integration
- Publishes `geometry.cgp.v1` to the gateway when configured.
- Uses `HIRAG_URL` to resolve `POST /geometry/event`.

## Make / Compose
- Included in `make up-agents` (agents stack) when enabled in compose.

