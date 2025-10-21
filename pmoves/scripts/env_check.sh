#!/usr/bin/env bash
# PMOVES Environment Preflight Check (Bash)
# Usage:
#   bash scripts/env_check.sh        # full scan
#   bash scripts/env_check.sh -q     # quick

set -euo pipefail
quick=0
[[ "${1:-}" == "-q" ]] && quick=1

have(){ command -v "$1" >/dev/null 2>&1; }
ver(){ ($@ --version 2>/dev/null || true) | head -n1 | tr -s ' '; }

echo
echo "== PMOVES Environment Check =="
echo "CWD: $(pwd)"
echo "OS:  $(uname -a || true)"
echo

echo "Commands:"
for c in rg git python python3 pip uv poetry conda node npm make docker docker-compose; do
  if have "$c"; then
    printf "[OK] %-14s %s\n" "$c" "$(ver "$c")"
  else
    printf "[--] %-14s\n" "$c"
  fi
done
if have docker; then
  if docker compose version >/dev/null 2>&1; then
    printf "[OK] %-14s %s\n" "compose" "$(docker compose version | head -n1 | tr -s ' ')"
  elif have docker-compose; then
    printf "[OK] %-14s %s\n" "compose" "$(docker-compose --version | tr -s ' ')"
  else
    printf "[--] %-14s\n" "compose"
  fi
fi

echo
echo "Repo shape:"
for d in services contracts schemas supabase neo4j n8n comfyui datasets docs; do
  if [[ -d "$d" ]]; then printf "%-14s %s\n" "$d:" "yes"; else printf "%-14s %s\n" "$d:" "no"; fi
done

echo
echo "Contracts:"
if [[ -f contracts/topics.json ]]; then
  if cat contracts/topics.json >/dev/null 2>&1; then
    echo "contracts/topics.json: valid"
    # Ensure summary topics exist and schema files are present
    need_topics=("health.weekly.summary.v1" "finance.monthly.summary.v1")
    for t in "${need_topics[@]}"; do
      if ! jq -e --arg T "$t" '.topics[$T]' contracts/topics.json >/dev/null 2>&1; then
        echo "WARN: missing topic in topics.json: $t"
      fi
    done
  else
    echo "contracts/topics.json: invalid"
  fi
else
  echo "contracts/topics.json: missing"
fi

echo
echo "Ports:"
ports=(6333 7474 8088 8085 3000 8087 8084 7700)
for p in "${ports[@]}"; do
  if command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:$p -sTCP:LISTEN -P -n >/dev/null 2>&1; then
      printf "%-6s %s\n" "$p" "LISTENING"
    else
      printf "%-6s %s\n" "$p" "free"
    fi
  else
    printf "%-6s %s\n" "$p" "(lsof not installed)"
  fi
done

echo
echo ".env status:"
if [[ -f .env ]]; then echo ".env present:       true"; else echo ".env present:       false"; fi
if [[ -f .env.example ]]; then echo ".env.example:       true"; else echo ".env.example:       false"; fi
if [[ -f env.shared ]]; then
  python3 <<'PY'
from __future__ import annotations

import pathlib

keys = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_REALTIME_KEY",
]

root = pathlib.Path(".")
shared = root / "env.shared"

def load_env(path: pathlib.Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        data[k] = v
    return data

shared_map = load_env(shared)
local_map = load_env(root / ".env")
local_local_map = load_env(root / ".env.local")

def fmt(key: str, value: str | None) -> str:
    if value is None:
        return "missing"
    if not value:
        return "blank"
    if key.endswith("_URL"):
        return "ok" if value.startswith("http") else "check"
    if value.startswith("sb_secret_") or value.startswith("sb_publishable_"):
        return "ok"
    return "check"

print("\nSupabase key sync:")
if not shared_map:
    print("  env.shared: missing keys")
else:
    for key in keys:
        src = shared_map.get(key)
        status = fmt(key, src)
        print(f"  {key:<26} env.shared={status}", end="")
        if status == "ok":
            if key.endswith("_KEY") and "SECRET" in key and not src.startswith("sb_secret_"):
                print(" (warn: expected sb_secret_)")
            else:
                print()
        else:
            print()
        for label, data in ((".env", local_map), (".env.local", local_local_map)):
            dst = data.get(key)
            match = "match" if dst == src and src not in (None, "") else ("missing" if dst is None else "mismatch")
            print(f"    ↳ {label:<11} {match}")
PY
fi

echo
echo "Mappers:"
if [[ -f tools/events_to_cgp.py ]]; then echo "events_to_cgp.py:   present"; else echo "events_to_cgp.py:   missing"; fi

echo
echo "Done."
