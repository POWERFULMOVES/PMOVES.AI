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
echo "Provider API Keys:"
if [[ -f env.shared ]]; then
  python3 <<'PY'
from __future__ import annotations

import pathlib

# Provider API keys - at least one recommended for LLM features
provider_keys = [
    ("OPENAI_API_KEY", "OpenAI"),
    ("ANTHROPIC_API_KEY", "Anthropic"),
    ("GROQ_API_KEY", "Groq"),
    ("GEMINI_API_KEY", "Google Gemini"),
    ("OLLAMA_BASE_URL", "Ollama (local)"),
]

# Optional keys for specific features
optional_keys = [
    ("ELEVENLABS_API_KEY", "ElevenLabs TTS"),
    ("VOYAGE_API_KEY", "Voyage AI Embeddings"),
    ("COHERE_API_KEY", "Cohere"),
    ("CLOUDFLARE_API_TOKEN", "Cloudflare Workers AI"),
    ("CLOUDFLARE_ACCOUNT_ID", "Cloudflare Account ID"),
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

print("  Core LLM Providers (at least one recommended):")
provider_count = 0
for key, name in provider_keys:
    value = shared_map.get(key)
    if value and value != "" and not value.startswith("your_"):
        provider_count += 1
        print(f"    ✓ {name:<20} configured")
    elif key == "OLLAMA_BASE_URL" and (value == "" or value is None):
        # Ollama with default URL is OK
        print(f"    • {name:<20} (will use http://localhost:11434)")
    else:
        print(f"    ✗ {name:<20} missing")

if provider_count == 0:
    print("  ⚠ No LLM providers configured - add at least one for LLM features")
    print("    Tip: Set OPENAI_API_KEY, GROQ_API_KEY, or use Ollama for local models")

print("\n  Optional API Keys:")
for key, name in optional_keys:
    value = shared_map.get(key)
    if value and value != "" and not value.startswith("your_"):
        print(f"    ✓ {name:<30} configured")
    else:
        print(f"    • {name:<30} not set (optional)")

# Check for empty but set keys (common mistake)
print("\n  Checking for empty values:")
empty_count = 0
for key, value in shared_map.items():
    if "API_KEY" in key or "TOKEN" in key:
        if value == "" or value.startswith("your_"):
            print(f"    ⚠ {key} is set but empty/placeholder")
            empty_count += 1
if empty_count == 0:
    print("    ✓ All API keys have values")
PY
else
  echo "  env.shared not found - run 'make bootstrap' to create it"
fi

echo
echo "Mappers:"
if [[ -f tools/events_to_cgp.py ]]; then echo "events_to_cgp.py:   present"; else echo "events_to_cgp.py:   missing"; fi

echo
echo "Done."
