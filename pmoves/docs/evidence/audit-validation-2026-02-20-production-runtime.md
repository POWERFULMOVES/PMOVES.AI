# PMOVES Production Runtime Remediation Evidence
# Date: 2026-02-20
# Branch: PMOVES.AI-Edition-Hardened

## Command Results

1) make -C pmoves smoke
- PASS
- status: ok
- warnings:
  - supabase_realtime_pmoves contains "realtime-dev" (Supabase CLI naming artifact)
  - realtime tenant health endpoint returned 403 (expected for local CLI auth)

2) make -C pmoves agents-headless-smoke
- PASS

3) make -C pmoves archon-smoke
- PASS

4) make -C pmoves monitoring-smoke
- PASS
- prom.ready: 200
- loki.ready: 200
- grafana.database: ok
- prom.targets: active=36 healthy=21
- grafana.dashboards: 20
- supabase.runtime: cli

5) make -C pmoves submodule-integrity
- PASS
- gitlinks mapped: 40
- drifted: 0
- conflicts: 0

6) make -C pmoves supa-env-doctor-strict
- PASS

## Runtime Repairs Applied

A) Supabase storage recovery
- Issue: supabase_storage_pmoves crash-looped with migration errors:
  - duplicate key / relation missing / permission denied for migrations
- Root cause: storage migrator role permissions/ownership drift
- Fix applied on postgres DB:
  - grant usage,create on schema storage to supabase_storage_admin
  - alter table storage.migrations owner to supabase_storage_admin
  - grant select,insert,update,delete on storage.migrations to supabase_storage_admin
- Result: supabase_storage_pmoves -> healthy

B) Collation mismatch warning cleanup
- Ran: ALTER DATABASE postgres REFRESH COLLATION VERSION;
- Result: datcollversion = 153.120; no new "collation version mismatch" logs observed after refresh

C) Production health probe correction
- Updated pmoves/scripts/codex_health_quick.py
  - Agent Zero default probe: http://localhost:8080/healthz
  - Fallback probe: http://localhost:8081/
  - Removed incorrect fallback to DeepResearch endpoint (:8098)

## Container Spot Check
- supabase_db_pmoves: healthy
- supabase_kong_pmoves: healthy
- supabase_realtime_pmoves: healthy
- supabase_storage_pmoves: healthy
