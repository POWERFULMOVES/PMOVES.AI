# DRAFT PR: feat(hermes-room): add hermes-agent gateway room to catalog

**Branch**: `feat/hermes-gateway-room`
**Base**: `origin/main`
**Commits**: `acc60bc9c`
**Status**: DRAFT -- room manifest may need port/node adjustments after fleet context
**Size**: 2 files, 363 lines

## Scope
- `hermes-agent.room.control.json`: room manifest for Hermes gateway
- `catalog.json`: registry entry for P7 stage manager

## Why Draft?
Room manifest includes `gateway_port: 7700` (elder-melchor local).
SPARK/B850 may need different ports or reverse proxy setup.
Need to confirm:
- Port availability on each node
- Whether gateway runs on all nodes or elder-melchor only (proxy to rest)
- P7 stage priority ordering with existing rooms

## Pre-merge Checklist
- [ ] Port conflict check on SPARK/B850
- [ ] P7 stage priority confirmed with existing room order
- [ ] Catalog.json schema validated against P7 contract
