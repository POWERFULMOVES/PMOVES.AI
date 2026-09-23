#!/usr/bin/env bash
set -euo pipefail

# Push KEY=VALUE pairs from an env file into GitHub Actions secrets.
# Defaults to pmoves/env.shared, but you can point at any KEY=VALUE file.

usage() {
  cat <<'EOF'
push-gh-secrets.sh [-f env_file] [-r owner/repo] [--env ENV] [--only key1,key2] [--all] [--manifest path] [--dry-run] [--ghcr-bootstrap] [--routed]

NOTE: GHCR auth now prefers the PMOVES.AI GitHub App (GH_APP_ID + GH_APP_SEC secrets).
      The --ghcr-bootstrap flag is a fallback for environments without a configured App.

Options:
  -f, --file     Path to env file (default: pmoves/env.shared)
  -r, --repo     GitHub repo in owner/name form (default: derive from git remote)
      --env      GitHub Actions environment name (e.g., Dev, Prod)
  --only     Comma-separated keys to include (others are skipped)
      --all      Push all keys (ignore manifest whitelist)
      --manifest Path to secrets manifest (default: pmoves/chit/secrets_manifest.yaml)
      --dry-run  Print actions instead of calling gh
      --ghcr-bootstrap              Also set GHCR_USERNAME + GHCR_TOKEN from existing credentials
      --ghcr-token-from KEY         Primary token key to read (default: GHCR_TOKEN)
      --ghcr-fallback-token-from KEY
                                    Fallback token key to read (default: GH_PAT_PUBLISH)
      --ghcr-username-from KEY      Username key to read (default: GHCR_USERNAME)
      --routed   Push each github_secret target of the v2 CHIT manifest to its
                 own repo/env (--manifest overrides the v2 default). A routed
                 target {name, repo, env} goes where it says; a bare name goes
                 to --repo/--env. Values come from the env file; names with no
                 value there are skipped. Honors --only and --dry-run.

Examples:
  ./pmoves/tools/push-gh-secrets.sh --repo POWERFULMOVES/PMOVES.AI --env Dev
  ./pmoves/tools/push-gh-secrets.sh --repo POWERFULMOVES/PMOVES.AI --env Dev --ghcr-bootstrap
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
GHCR_BOOTSTRAP=0
GHCR_TOKEN_FROM="GHCR_TOKEN"
GHCR_FALLBACK_TOKEN_FROM="GH_PAT_PUBLISH"
GHCR_USERNAME_FROM="GHCR_USERNAME"
ROUTED=0
MANIFEST_SET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file) ENV_FILE="$2"; shift 2;;
    -r|--repo) GH_REPO="$2"; shift 2;;
    --env) GH_ENV="$2"; shift 2;;
    --only) ONLY_KEYS="$2"; shift 2;;
    --manifest) MANIFEST="$2"; MANIFEST_SET=1; shift 2;;
    --all) PUSH_ALL=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    --ghcr-bootstrap) GHCR_BOOTSTRAP=1; shift;;
    --ghcr-token-from) GHCR_TOKEN_FROM="$2"; shift 2;;
    --ghcr-fallback-token-from) GHCR_FALLBACK_TOKEN_FROM="$2"; shift 2;;
    --ghcr-username-from) GHCR_USERNAME_FROM="$2"; shift 2;;
    --routed) ROUTED=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

if [[ $ROUTED -eq 1 && $GHCR_BOOTSTRAP -eq 1 ]]; then
  echo "--routed and --ghcr-bootstrap are separate runs; pass one." >&2
  exit 1
fi

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

# --routed: one push per manifest route (name, repo, env). The routes come from
# github_secret_targets.py, the one definition of the target format, so this
# script never parses the manifest itself. Names and routes are printed; values
# only ever travel on gh's stdin.
push_routed() {
  local py="${PYTHON:-}"
  if [[ -z "$py" ]]; then
    py="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
  fi
  if [[ -z "$py" ]]; then
    echo "python not found; --routed needs it to read the manifest." >&2
    exit 1
  fi
  local emitter
  emitter="$(dirname "${BASH_SOURCE[0]}")/github_secret_targets.py"
  local emit_args=(routes --default-repo "$GH_REPO" --default-env "$GH_ENV")
  if [[ $MANIFEST_SET -eq 1 ]]; then
    emit_args+=(--manifest "$MANIFEST")
  fi
  local routes
  if ! routes="$("$py" "$emitter" "${emit_args[@]}")"; then
    echo "Could not read github_secret routes from the manifest; nothing pushed." >&2
    exit 1
  fi
  routes="${routes//$'\r'/}"

  # Same parse as the default mode below: first occurrence of a key wins.
  local -A values=()
  local line key val
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *"="* ]] && continue
    key=${line%%=*}
    val=${line#*=}
    key=${key//[$'\t ']/}
    [[ -z "$key" ]] && continue
    [[ -n "${values[$key]+set}" ]] || values[$key]="$val"
  done < "$ENV_FILE"

  local name repo env wanted k
  local env_args=()
  while IFS=$'\t' read -r name repo env; do
    [[ -z "$name" ]] && continue
    if [[ -n "$ONLY_KEYS" ]]; then
      wanted=0
      for k in "${ONLY_ARR[@]}"; do
        if [[ "$k" == "$name" ]]; then wanted=1; fi
      done
      [[ $wanted -eq 1 ]] || continue
    fi
    if [[ -z "${values[$name]+set}" ]]; then
      echo "Skip $name for $repo${env:+ (env $env)}: no value in $ENV_FILE" >&2
      continue
    fi
    env_args=()
    if [[ -n "$env" ]]; then env_args=(--env "$env"); fi
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY-RUN: would set $name in $repo${env:+ (env $env)}"
    else
      printf '%s' "${values[$name]}" | gh secret set "$name" --repo "$repo" --app actions "${env_args[@]}" >/dev/null
      echo "Set $name in $repo${env:+ (env $env)}"
    fi
  done <<< "$routes"
}

if [[ $ROUTED -eq 1 ]]; then
  push_routed
  exit 0
fi

# Initialize empty array to avoid unbound variable errors under set -u
MANIFEST_KEYS=()
PUSHED_KEYS=""

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
  if [[ $PUSH_ALL -eq 1 || ${#MANIFEST_KEYS[@]} -eq 0 ]]; then
    return 0
  fi
  for k in "${MANIFEST_KEYS[@]}"; do
    if [[ "$k" == "$key" ]]; then return 0; fi
  done
  return 1
}

lookup_value() {
  local key="$1"
  local shell_val="${!key:-}"
  if [[ -n "$shell_val" ]]; then
    printf '%s' "$shell_val"
    return 0
  fi
  local line
  line=$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)
  if [[ -n "$line" ]]; then
    printf '%s' "${line#*=}"
    return 0
  fi
  return 1
}

set_secret() {
  local key="$1"
  local value="$2"
  if [[ " $PUSHED_KEYS " == *" $key "* ]]; then
    return 0
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: would set $key in $GH_REPO${GH_ENV:+ (env $GH_ENV)}"
  else
    printf '%s' "$value" | gh secret set "$key" --repo "$GH_REPO" --app actions ${GH_ENV:+--env "$GH_ENV"} >/dev/null
    echo "Set $key in $GH_REPO${GH_ENV:+ (env $GH_ENV)}"
  fi
  PUSHED_KEYS="$PUSHED_KEYS $key"
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
  if [[ $GHCR_BOOTSTRAP -eq 1 && "$key" == GHCR_* ]]; then
    # Avoid pushing placeholder GHCR_* values from env file before bootstrap resolution.
    continue
  fi
  set_secret "$key" "$val"
done < "$ENV_FILE"

if [[ $GHCR_BOOTSTRAP -eq 1 ]]; then
  ghcr_user="$(lookup_value "$GHCR_USERNAME_FROM" || true)"
  ghcr_token="$(lookup_value "$GHCR_TOKEN_FROM" || true)"
  if [[ -z "$ghcr_token" ]]; then
    ghcr_token="$(lookup_value "$GHCR_FALLBACK_TOKEN_FROM" || true)"
  fi
  if [[ -z "$ghcr_token" ]]; then
    ghcr_token="$(gh auth token 2>/dev/null || true)"
    if [[ -n "$ghcr_token" ]]; then
      echo "ℹ Using gh CLI token as GHCR fallback (ensure write:packages scope)"
    fi
  fi
  if [[ -z "$ghcr_user" ]]; then
    ghcr_user="${GITHUB_ACTOR:-}"
  fi
  if [[ -z "$ghcr_user" ]]; then
    ghcr_user="$(gh api user -q .login 2>/dev/null || true)"
  fi
  if [[ -z "$ghcr_user" || -z "$ghcr_token" ]]; then
    echo "✖ GHCR bootstrap failed: could not resolve username/token." >&2
    echo "  Checked username key: $GHCR_USERNAME_FROM" >&2
    echo "  Checked token keys: $GHCR_TOKEN_FROM, $GHCR_FALLBACK_TOKEN_FROM" >&2
    exit 1
  fi
  set_secret "GHCR_USERNAME" "$ghcr_user"
  set_secret "GHCR_TOKEN" "$ghcr_token"
fi
