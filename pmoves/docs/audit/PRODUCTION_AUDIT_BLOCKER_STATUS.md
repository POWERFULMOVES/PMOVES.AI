# Production Audit — Blocker Status

Last updated: 2026-02-17

## Summary

| ID | Blocker | Status | Resolution |
|----|---------|--------|------------|
| B1 | Orphaned gitlink `deskdesktop` | RESOLVED (phantom) | No such entry in git index. Error from nested submodules only. Already in `known_path_typos`. |
| B2 | Missing smoke Make targets | RESOLVED (phantom) | All targets exist in `pmoves/Makefile`: `smoke` (L1337), `smoke-gpu` (L1350), `verify-all` (L1026), `monitoring-smoke-prod` (L1516). |
| B3 | CHIT/CGP schema inconsistency | FIXED | Standardised all producers to `chit.cgp.v0.2`. `CGP_SPEC_VERSION` constant in `pmoves/chit/__init__.py`. |
| B4 | NATS Geometry Bus streams not auto-created | FIXED | Added `nats-init` sidecar service + `init_streams.sh` for idempotent stream creation on startup. |
| B5 | GHCR builds failing (platform dupes) | FIXED | Removed duplicate `linux/arm64` entries from 5 matrix lines. Triggers remain disabled pending runner stabilisation. |

---

## B1: Orphaned gitlink `deskdesktop` — PHANTOM

The git index contains only the correct `PMOVES-E2B-Danger-Room-Desktop`.
The `deskdesktop` typo is catalogued in `submodule_layer_validation_manifest.json`
under `known_path_typos` for detection. The recursive traversal error (`exit 128`)
comes from nested submodules inside Archon/BoTZ that have their own unmapped
gitlinks — this is a nested-submodule issue, not a top-level one.

## B2: Missing smoke Make targets — PHANTOM

All smoke targets are fully implemented in `pmoves/Makefile`:
- `smoke` (line 1337) — cross-platform dispatch (PowerShell / bash)
- `smoke-gpu` (line 1350) — Hi-RAG v2 GPU rerank validation
- `verify-all` (line 1026) — 11-step sequential orchestration
- `monitoring-smoke-prod` (line 1516) — Prometheus job health + target ratio
- `smoke-showtime` (`preflight.mk` line 151) — live watcher + full smoke suite

The earlier audit report may have tested from wrong directory or wrong shell.

## B3: CHIT/CGP Schema Standardisation — FIXED

Three incompatible CGP version strings were in production:
- Consciousness Service: `"version": "cgp.v1"` (custom, non-standard)
- Gateway/Hi-RAG/Agent Zero: `"type": "geometry.cgp.v1"` (hybrid wrapper)
- TypeScript generator (canonical): `"spec": "chit.cgp.v0.2"`

All Python services now use `"spec": "chit.cgp.v0.2"` via the
`CGP_SPEC_VERSION` constant in `pmoves/chit/__init__.py`. The gateway
accepts both `geometry.cgp.v1` (legacy) and `chit.cgp.v0.2` event types
for backward compatibility.

Files modified:
- `pmoves/chit/__init__.py` — version constant updated to v0.2
- `pmoves/services/consciousness-service/cgp_mapper.py` — already v0.2
- `pmoves/services/consciousness-service/tests/test_cgp_mapper.py` — assertions updated
- `pmoves/services/gateway/gateway/api/chit.py` — accepts both event types
- `pmoves/services/gateway/gateway/api/consciousness.py` — spec bumped
- `pmoves/services/common/shape_store.py` — spec + event handler updated
- `pmoves/services/common/cgp_mappers.py` — spec bumped
- `pmoves/services/agent-zero/mcp_server.py` — event type updated
- `pmoves/services/deepresearch/worker.py` — spec bumped
- `pmoves/services/gateway/tests/test_geometry_endpoints.py` — test payloads updated

## B4: NATS Geometry Bus Auto-Init — FIXED

JetStream is enabled (`-js` flag) but streams were not auto-created.

Added:
- `pmoves/scripts/nats/init_streams.sh` — Non-interactive, idempotent stream
  creation script (uses `--defaults` flag, no interactive prompts)
- `pmoves/docker-compose.yml` — `nats-init` sidecar service using
  `natsio/nats-box:0.14.5`, depends on NATS health, runs init script, exits.

Streams created:
- `GEOMETRY_CGP` — `geometry.>`, limits retention, 30d, 1GB
- `TOKENISM_ATTRIBUTION` — `tokenism.>`, interest retention, 90d, 2GB
- `BOTZ_COORDINATION` — `botz.>`, limits retention, 7d, 500MB

## B5: GHCR Workflow Fix — FIXED

1. Duplicate `linux/arm64` platform entries removed from 5 matrix lines
   (archon-ui, wger, firefly-iii, pmoves-yt, supaserch).
2. Jellyfin Dockerfile verified present at `pmoves/images/jellyfin/Dockerfile`.
3. Automatic triggers remain disabled (commented out) pending
   `ci-runners-lockdown-strict` runner lane stabilisation. This is intentional
   and documented in the workflow file.
