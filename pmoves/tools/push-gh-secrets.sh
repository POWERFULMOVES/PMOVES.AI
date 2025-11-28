#!/usr/bin/env bash
set -euo pipefail

# Push KEY=VALUE pairs from an env file into GitHub Actions secrets.
# Defaults to pmoves/env.shared, but you can point at any KEY=VALUE file.

usage() {
  cat <<'EOF'
push-gh-secrets.sh [-f env_file] [-r owner/repo] [--env ENV] [--only key1,key2] [--all] [--manifest path] [--dry-run]

Options:
  -f, --file     Path to env file (default: pmoves/env.shared)
  -r, --repo     GitHub repo in owner/name form (default: derive from git remote)
      --env      GitHub Actions environment name (e.g., Dev, Prod)
      --only     Comma-separated keys to include (others are skipped)
      --all      Push all keys (ignore manifest whitelist)
      --manifest Path to secrets manifest (default: pmoves/chit/secrets_manifest.yaml)
      --dry-run  Print actions instead of calling gh

Examples:
  ./pmoves/tools/push-gh-secrets.sh --repo POWERFULMOVES/PMOVES.AI --env Dev
  ./pmoves/tools/push-gh-secrets.sh --only SUPABASE_SERVICE_ROLE_KEY,SUPABASE_JWT_SECRET
EOF
}

ENV_FILE="pmoves/env.shared"
GH_REPO=""
GH_ENV=""
ONLY_KEYS=""
DRY_RUN=0
PUSH_ALL=0
MANIFEST="pmoves/chit/secrets_manifest.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file) ENV_FILE="$2"; shift 2;;
    -r|--repo) GH_REPO="$2"; shift 2;;
    --env) GH_ENV="$2"; shift 2;;
    --only) ONLY_KEYS="$2"; shift 2;;
    --manifest) MANIFEST="$2"; shift 2;;
    --all) PUSH_ALL=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "$GH_REPO" ]]; then
  origin=$(git config --get remote.origin.url || true)
  if [[ "$origin" =~ github.com[:/](.+/.+)\.git ]]; then
    GH_REPO="${BASH_REMATCH[1]}"
  fi
fi

if [[ -z "$GH_REPO" ]]; then
  echo "GitHub repo not set. Use --repo owner/name." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) not found. Install it first." >&2
  exit 1
fi

if [[ -n "$ONLY_KEYS" ]]; then
  IFS=',' read -r -a ONLY_ARR <<< "$ONLY_KEYS"
fi

if [[ $PUSH_ALL -eq 0 && -z "$ONLY_KEYS" && -f "$MANIFEST" ]]; then
  mapfile -t MANIFEST_KEYS < <(grep -E '^[[:space:]]+key:' "$MANIFEST" | awk '{print $2}' | sort -u)
fi

should_include() {
  local key="$1"
  if [[ -n "$ONLY_KEYS" ]]; then
    for k in "${ONLY_ARR[@]}"; do
      if [[ "$k" == "$key" ]]; then return 0; fi
    done
    return 1
  fi
  if [[ $PUSH_ALL -eq 1 || ${#MANIFEST_KEYS[@]:-0} -eq 0 ]]; then
    return 0
  fi
  for k in "${MANIFEST_KEYS[@]}"; do
    if [[ "$k" == "$key" ]]; then return 0; fi
  done
  return 1
}

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  if [[ "$line" != *"="* ]]; then
    continue
  fi
  key=${line%%=*}
  val=${line#*=}
  key=${key//[$'\t ']/}
  [[ -z "$key" ]] && continue
  if ! should_include "$key"; then
    continue
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: would set $key in $GH_REPO${GH_ENV:+ (env $GH_ENV)}"
  else
    printf '%s' "$val" | gh secret set "$key" --repo "$GH_REPO" --app actions ${GH_ENV:+--env "$GH_ENV"} >/dev/null
    echo "Set $key in $GH_REPO${GH_ENV:+ (env $GH_ENV)}"
  fi
done < "$ENV_FILE"
