#!/usr/bin/env python3
"""Lane 3 supabase-stack-default-up — full orchestrator.

Run after a fresh checkout to bring up the supabase stack end-to-end:

  python tools/bootstrap-supabase-stack.py
  # or via Makefile:
  make supa-stack-default-up

Steps:
  1. Bring up supabase-db (need it running before any password alignment)
  2. Generate fresh secrets (env.tier-supabase)
  3. Align env.shared (replace ${VAR} refs with literals, add POSTGRES_PASSWORD_URLENCODED)
  4. Align env.tier-ui (populate empty SUPABASE_* values)
  5. Run bootstrap_db.sh to align DB password (requires db up)
  6. Run kong migrations (kong needs its postgres schema initialized)
  7. Bring up the rest of supabase-local (kong, gotrue, postgrest, realtime, storage, ...)
  8. Configure kong routes (auth, rest, realtime, storage, meta)
  9. Verify pmoves-ui /api/health + capture evidence

All subprocess paths are relative to REPO (pmoves/) — do NOT prefix with pmoves/,
that double-nests.

Lane 3 PR: chore/supabase-stack-default-up
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]  # pmoves/


def run(cmd: str, check: bool = True, capture: bool = False) -> str:
    print(f"\n+ {cmd}")
    r = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO),
    )
    if check and r.returncode != 0:
        print(f"  ! rc={r.returncode}")
        if r.stderr:
            print(f"  stderr: {r.stderr[:500]}")
        if r.stdout:
            print(f"  stdout: {r.stdout[:500]}")
        sys.exit(1)
    return (r.stdout or "") + (r.stderr or "")


def step(title: str):
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-verify", action="store_true", help="skip final pmoves-ui health check")
    p.add_argument("--skip-kong-routes", action="store_true", help="skip kong route configuration")
    p.add_argument("--no-restart", action="store_true", help="don't restart running supabase services")
    args = p.parse_args()

    # 1. Bring up supabase-db FIRST (bootstrap_db.sh needs a running db)
    step("Step 1/9: Bring up supabase-db (prerequisite for password alignment)")
    if not args.no_restart:
        run(
            "docker compose --project-directory . --env-file env.shared "
            "--env-file env.tier-supabase -f docker-compose.yml "
            "--profile supabase-local up -d supabase-db"
        )
    run(
        "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do "
        "  s=$(docker inspect --format '{{.State.Health.Status}}' pmoves-supabase-db-1 2>&1); "
        "  if [ \"$s\" = \"healthy\" ]; then echo \"db healthy\"; break; fi; "
        "  echo \"waiting db... $s\"; sleep 2; "
        "done"
    )

    # 2. Generate fresh secrets
    step("Step 2/9: Generate fresh secrets → env.tier-supabase")
    tier_supa = REPO / "env.tier-supabase"
    if tier_supa.exists():
        with tier_supa.open(encoding="utf-8") as f:
            current = f.read()
        if "your_jwt_secret_here" in current or "PLACEHOLDER" in current:
            print("env.tier-supabase has placeholders, regenerating...")
            run(
                "bash -c 'bash scripts/supabase/generate-keys.sh 2>/dev/null' > env.tier-supabase",
                capture=True,
            )
        else:
            print("env.tier-supabase already has real values, skipping")
    else:
        run(
            "bash -c 'bash scripts/supabase/generate-keys.sh 2>/dev/null' > env.tier-supabase",
            capture=True,
        )

    # 3. Align env.shared
    step("Step 3/9: Align env.shared (replace ${VAR} refs with literals)")
    run("python tools/fix-env-shared.py", capture=True)

    # 4. Align env.tier-ui
    step("Step 4/9: Align env.tier-ui (populate empty SUPABASE_* values)")
    run("python tools/fix-env-tier-ui.py", capture=True)

    # 5. Run bootstrap_db.sh (now db is up)
    step("Step 5/9: Run bootstrap_db.sh to align DB password")
    run("bash scripts/supabase/bootstrap_db.sh")

    # 6. Run kong migrations
    step("Step 6/9: Run kong migrations (kong needs its postgres schema initialized)")
    run(
        "docker run --rm --network pmoves_data "
        "-e KONG_DATABASE=postgres -e KONG_PG_HOST=supabase-db -e KONG_PG_DATABASE=pmoves "
        "-e KONG_PG_USER=pmoves -e KONG_PG_PASSWORD=$(grep ^POSTGRES_PASSWORD= env.shared | cut -d= -f2) "
        "kong/kong:3.9.1 sh -c 'kong migrations bootstrap -y 2>&1 | tail -5; kong migrations up -y 2>&1 | tail -5'",
        capture=True,
    )

    # 7. Bring up the rest
    step("Step 7/9: Bring up supabase-kong, gotrue, postgrest, realtime, storage, etc.")
    if not args.no_restart:
        run(
            "docker compose --project-directory . --env-file env.shared "
            "--env-file env.tier-supabase -f docker-compose.yml "
            "--profile supabase-local up -d supabase-kong supabase-postgrest supabase-realtime "
            "supabase-storage supabase-imgproxy supabase-meta supabase-studio supabase-edge-functions "
            "supabase-analytics supabase-vector supabase-pooler"
        )

    # Wait for kong to be healthy
    run(
        "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do "
        "  s=$(docker inspect --format '{{.State.Health.Status}}' pmoves-supabase-kong-1 2>&1); "
        "  if [ \"$s\" = \"healthy\" ]; then echo \"kong healthy\"; break; fi; "
        "  echo \"waiting kong... $s\"; sleep 2; "
        "done"
    )

    # 8. Configure kong routes
    if not args.skip_kong_routes:
        step("Step 8/9: Configure kong routes (auth, rest, realtime, storage, meta)")
        for name, url in [
            ("auth", "http://supabase-gotrue:9999"),
            ("rest", "http://supabase-postgrest:3000"),
            ("realtime", "http://supabase-realtime:4000"),
            ("storage", "http://supabase-storage:5000"),
            ("meta", "http://supabase-meta:8080"),
        ]:
            run(
                f"curl -s -X POST http://localhost:8001/services "
                f"-H 'Content-Type: application/json' -d '{{\"name\":\"{name}\",\"url\":\"{url}\"}}'",
                check=False,
                capture=True,
            )
        for name, paths in [
            ("auth", "/auth/v1"),
            ("rest", "/rest/v1"),
            ("realtime", "/realtime/v1"),
            ("storage", "/storage/v1"),
            ("meta", "/pg"),
        ]:
            run(
                f"curl -s -X POST http://localhost:8001/services/{name}/routes "
                f"-H 'Content-Type: application/json' -d '{{\"paths\":[\"{paths}\"]}}'",
                check=False,
                capture=True,
            )

    # 9. Verify
    if not args.skip_verify:
        step("Step 9/9: Verify pmoves-ui /api/health + capture evidence")
        run("python tools/lane3_capture.py", capture=True)
        run("python tools/lane3_screenshots.py", capture=True)

    print("\nLane 3 bootstrap complete. Evidence in tools/lane3-evidence/")


if __name__ == "__main__":
    main()
