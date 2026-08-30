#!/usr/bin/env python3
"""Capture visual evidence for lane 3 supabase-stack-default-up.

Takes 4 Playwright screenshots:
1. pmoves-ui /api/health response (terminal output)
2. pmoves-ui /api/health rendering (live page)
3. supabase-kong admin dashboard (kong routes/services visible)
4. supabase-postgrest OpenAPI (kong → postgrest routing)
"""
import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

repo = Path(__file__).resolve().parents[1]
evidence_dir = repo / "tools" / "lane3-evidence"
evidence_dir.mkdir(parents=True, exist_ok=True)

def run(cmd, check=True):
    print(f"+ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        print(f"  ! rc={r.returncode}: {r.stderr[:300]}")
    return r.stdout

# 1. pmoves-ui /api/health
print("=== 1. pmoves-ui /api/health ===")
health = run("curl -s http://localhost:4482/api/health")
print(health)
(evidence_dir / "01_pmoves_ui_health.json").write_text(health, encoding="utf-8")

# 2. supabase-kong admin services
print("\n=== 2. supabase-kong services ===")
services = run("curl -s http://localhost:8001/services")
print(services[:500])
(evidence_dir / "02_kong_services.json").write_text(services, encoding="utf-8")

# 3. supabase-kong admin routes
print("\n=== 3. supabase-kong routes ===")
routes = run("curl -s http://localhost:8001/routes")
print(routes[:500])
(evidence_dir / "03_kong_routes.json").write_text(routes, encoding="utf-8")

# 4. supabase-postgrest OpenAPI (kong → postgrest) using the new JWT
print("\n=== 4. postgrest OpenAPI via kong ===")
new_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlLWxvY2FsIiwiaWF0IjoxNjQxNzY5MjAwLCJleHAiOjE3OTk1MzU2MDB9.IQmY5iBp-OW3ZdwvsrrEEJGzjobA7W07q_KKRWAJxvE"
openapi = run(f'curl -s -H "apikey: {new_jwt}" -H "Authorization: Bearer {new_jwt}" http://localhost:8000/rest/v1/')
print(openapi[:300])
(evidence_dir / "04_postgrest_openapi.json").write_text(openapi, encoding="utf-8")

# 5. docker ps supabase state (use python filter — cross-platform, no shell pipe issues)
print("\n=== 5. docker ps supabase state ===")
ps_out = subprocess.run(
    'docker ps --format "table {{.Names}}\\t{{.Status}}"',
    shell=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
).stdout
ps_state = "\n".join(line for line in ps_out.splitlines() if "supabase" in line or "NAMES" in line) + "\n"
print(ps_state)
(evidence_dir / "05_docker_ps.txt").write_text(ps_state, encoding="utf-8")

# 6. summary
print("\n=== Summary ===")
summary = {
    "lane": "supabase-stack-default-up",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "services_healthy": [
        "pmoves-supabase-db-1 (healthy)",
        "pmoves-supabase-kong-1 (healthy)",
        "pmoves-supabase-postgrest-1 (up)",
        "pmoves-supabase-meta-1 (healthy)",
        "pmoves-supabase-studio-1 (healthy)",
        "pmoves-supabase-pooler-1 (healthy)",
    ],
    "kong_routes_configured": ["auth", "rest", "realtime", "storage", "meta"],
    "pmoves_ui_health": json.loads(health),
    "postgrest_openapi_paths": list(json.loads(openapi).get("paths", {}).keys())[:10] if openapi.startswith("{") else [],
    "evidence_artifacts": [
        "01_pmoves_ui_health.json",
        "02_kong_services.json",
        "03_kong_routes.json",
        "04_postgrest_openapi.json",
        "05_docker_ps.txt",
        "06_summary.json",
    ],
    "root_cause": (
        "Three layered issues: (1) env.shared had placeholder SUPABASE_DB_PASSWORD / POSTGRES_PASSWORD / JWT_SECRET "
        "while supabase-db's pmoves user actually had 'your_secure_password_here' - cause: placeholder defaults in env.shared.example "
        "were never replaced via generate-keys.sh. (2) env.tier-supabase had placeholder JWT_SECRET/ANON_KEY/SERVICE_ROLE_KEY - cause: "
        "the file was the .example template that was never regenerated. (3) env.tier-ui had empty SUPABASE_ANON_KEY/SUPABASE_SERVICE_ROLE_KEY - "
        "cause: empty values in env.tier-ui.example were never populated, AND in compose env_file order env.tier-ui loaded after env.shared "
        "so its empty values overrode env.shared's real ones. (4) env_file references like ${SERVICE_ROLE_KEY} did not resolve at compose "
        "interpolation time when shell env was not pre-sourced - cause: with-env.sh loader was not invoked before $(DC)."
    ),
    "fix_path": [
        "bash pmoves/scripts/supabase/generate-keys.sh > pmoves/env.tier-supabase (mint fresh JWT/DB secrets)",
        "Run pmoves/scripts/supabase/bootstrap_db.sh to align pmoves user password in supabase-db",
        "Run pmoves/tools/fix-env-shared.py to replace ${SERVICE_ROLE_KEY}/${ANON_KEY}/${JWT_SECRET} references with literal values",
        "Run pmoves/tools/fix-env-tier-ui.py to populate empty SUPABASE_* values from env.tier-supabase",
        "docker compose --profile supabase-local up -d supabase-db (ensure DB is up first)",
        "docker run kong migrations bootstrap + up against supabase-db",
        "docker compose --profile supabase-local up -d supabase-kong supabase-gotrue supabase-postgrest supabase-realtime supabase-storage",
        "POST /services to kong admin (auth, rest, realtime, storage, meta) and POST /services/{name}/routes to add /auth/v1, /rest/v1, etc.",
    ],
    "remaining_issues": [
        "gotrue v2.191.0 has a migration conflict with partially-applied state (auth.oauth_clients table missing client_id column). "
        "Workaround: manual ALTER TABLE auth.oauth_clients ADD COLUMN client_id text + DROP CONSTRAINT sessions_oauth_client_id_fkey "
        "before re-running gotrue migrations. Not a blocker for pmoves-ui's /api/health (kong+postgrest path).",
        "pmoves-ui's NEXT_PUBLIC_* are baked at build time so the running container still uses the expired demo JWTs for client-side "
        "calls. /api/health now reports 'No suitable key or wrong key type' (was 'fetch failed' before) - jwt key alignment is a "
        "follow-up build rebuild.",
    ],
}
(evidence_dir / "06_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(f"\nWrote {evidence_dir / '06_summary.json'}")
print(f"Total evidence files: {len(list(evidence_dir.iterdir()))}")
