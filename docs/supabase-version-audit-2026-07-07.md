# Supabase Version & Configuration Audit — 2026-07-07

## Edge-Functions Healthcheck Bug (FIXED in #1994)

The edge-functions healthcheck used `curl` which is not available in the edge-runtime image. Fixed to use bash TCP socket test per official Supabase pattern.

## Image Version Alignment (This PR)

All image versions aligned with `PMOVES-supabase/docker/docker-compose.yml` (the custom fork that serves as canonical upstream reference for PMOVES.AI).

| Service | Previous | Updated | Reference |
|---------|----------|---------|-----------|
| edge-runtime | v1.70.0 | v1.74.0 | Official fork |
| postgrest | v14.3 | v14.12 | Official fork |
| postgres-meta | v0.95.2 | v0.96.6 | Official fork |
| kong | 3.7.1 (`kong`) | 3.9.1 (`kong/kong`) | Official fork — image name fix |
| realtime | v2.72.0 | v2.102.3 | Official fork — added METRICS_JWT_SECRET |
| storage-api | v1.37.1 | v1.60.4 | Official fork |
| supavisor | 2.7.4 | 2.9.5 | Official fork |
| studio | 2026.02.04 | 2026.06.03 | Official fork |

## Breaking Changes Addressed

### Realtime v2.102.3
New environment variable added: `METRICS_JWT_SECRET=${JWT_SECRET}`
(RLIMIT_NOFILE, SEED_SELF_HOST, RUN_JANITOR, SECRET_KEY_BASE already present in PMOVES compose)

### Kong Image Name
Official Supabase uses `kong/kong:3.9.1` (Kong's own registry), not `kong:3.7.1` (Docker Hub).

## Services Not Changed
- **gotrue**: PMOVES v2.191.0 is NEWER than official v2.189.0
- **postgres**: PMOVES on PG17 (17.6.1.108) vs official PG15 — intentional upgrade
- **imgproxy**: v3.30.1 — matches official
- **logflare/vector**: PMOVES-specific additions not in official compose

## Purpose of PMOVES-supabase Custom Fork

The PMOVES-supabase submodule tracks the official Supabase docker-compose.yml as the canonical reference for image versions, environment variables, and service configuration. PMOVES.AI's compose files fork from this reference, adding hardening (cap_drop, no-new-privileges, host-leak-guard), custom network topology, and split compose overlays.
