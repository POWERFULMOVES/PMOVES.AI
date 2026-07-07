# Supabase Version & Configuration Audit — 2026-07-07

## 1. Edge-Functions Healthcheck Bug (FIXED in this PR)

### Problem
PMOVES added a healthcheck `curl -sSf http://localhost:9000/health` to the
edge-functions service. The `supabase/edge-runtime` image does NOT include
curl, wget, or deno in PATH — the healthcheck fails on every check (FailingStreak: 183).

### Root Cause
The official Supabase docker-compose does NOT use curl for edge-functions.
It uses a pure bash TCP socket test:
```
test: ["CMD-SHELL", "timeout 1 bash -c '</dev/tcp/127.0.0.1/9000'"]
```

PMOVES fork replaced this with a curl-based check that the image cannot satisfy.

### Fix
Replaced the broken curl healthcheck with the official TCP socket pattern.

## 2. Image Version Drift (PMOVES vs Official Upstream)

| Service | PMOVES Version | Official Version | Gap |
|---------|---------------|-----------------|-----|
| edge-runtime | v1.70.0 | v1.74.0 | 4 minor versions |
| kong | 3.7.1 | 3.9.1 | 2 minor versions (image name also differs: `kong` vs `kong/kong`) |
| postgrest | v14.3 | v14.12 | 9 patch versions |
| realtime | v2.72.0 | v2.102.3 | 30 minor versions (significant) |
| storage-api | v1.37.1 | v1.60.4 | 23 minor versions (significant) |
| studio | 2026.02.04 | 2026.06.03 | 4 months behind |
| supavisor | 2.7.4 | 2.9.5 | 2 minor versions |
| postgres-meta | v0.95.2 | v0.96.6 | 1 minor + 4 patches |
| gotrue | v2.191.0 | v2.189.0 | PMOVES is NEWER |
| postgres | 17.6.1.108 | 15.8.1.085 | PMOVES on PG17 (intentional) |
| logflare | 1.30.3 | — | Not in official compose |
| vector | 0.28.1-alpine | — | Not in official compose |
| imgproxy | v3.30.1 | v3.30.1 | ✅ Match |

### Priority Upgrade Recommendations
1. **P0 — realtime v2.72→v2.102**: 30 versions behind, likely security fixes
2. **P0 — storage-api v1.37→v1.60**: 23 versions behind, major feature/security gap
3. **P1 — postgrest v14.3→v14.12**: 9 patches behind
4. **P1 — edge-runtime v1.70→v1.74**: New features + fixes
5. **P2 — studio**: UI features, non-critical
6. **P2 — kong 3.7→3.9**: Also fix image name from `kong` to `kong/kong`

## 3. Kong Image Name Mismatch

PMOVES uses `kong:3.7.1` (Docker Hub official).
Official Supabase uses `kong/kong:3.9.1` (Kong's own registry).
The `kong/kong` image is the recommended source going forward.

## 4. Services Without Healthchecks

These PMOVES supabase services have NO healthcheck defined:
- `supabase-postgrest` — distroless image, no shell (note in compose)
- `supabase-storage` — `service_started` condition only

Official Supabase defines healthchecks for these. Consider adding:
- postgrest: TCP socket test on :3000
- storage-api: TCP socket test on :5000

