#!/usr/bin/env bash
# PMOVES Interactive .env Setup (Bash)
#
# Usage:
#   bash scripts/env_setup.sh              # interactive prompts
#   bash scripts/env_setup.sh -y           # non-interactive; accept defaults where possible
#   bash scripts/env_setup.sh --from PROVIDER  # doppler|infisical|1password|sops

set -euo pipefail
cd "$(dirname "$0")/.."  # into pmoves/

force=0
yes=0
provider="none"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--force) force=1; shift ;;
    -y|--yes) yes=1; shift ;;
    --from) provider="${2:-none}"; shift 2 ;;
    *) shift ;;
  esac
done

have(){ command -v "$1" >/dev/null 2>&1; }
is_secret(){ [[ "$1" =~ (SECRET|TOKEN|PASSWORD|API_KEY|ACCESS_KEY|PRIVATE|WEBHOOK) ]]; }
suggest_default(){
  case "$1" in
    *PRESIGN_SHARED_SECRET*) python - <<'PY'
import base64,uuid
print(base64.b64encode(uuid.uuid4().bytes).decode())
PY
      ;;
    *MINIO_ACCESS_KEY*) echo "pmoves" ;;
    *MINIO_SECRET_KEY*) echo "password" ;;
    *NATS_URL*) echo "nats://nats:4222" ;;
    *JELLYFIN_URL*) echo "http://jellyfin:8096" ;;
    *AWS_DEFAULT_REGION*) echo "us-east-1" ;;
    *) echo "" ;;
  esac
}

pull_from_provider(){
  local p="$1" out=".env.generated"
  case "$p" in
    doppler)
      if have doppler; then doppler secrets download --no-file --format env > "$out" && echo "Imported secrets from Doppler -> $out"; fi ;;
    infisical)
      if have infisical; then infisical export --format=dotenv > "$out" && echo "Imported secrets from Infisical -> $out"; fi ;;
    1password)
      if have op; then op item get PMOVES_ENV --format json | jq -r '.fields[]|select(.id and .value)|"\(.id)=\(.value)"' > "$out" && echo "Imported secrets from 1Password -> $out"; fi ;;
    sops)
      if have sops && [[ -f .env.sops ]]; then sops -d .env.sops > "$out" && echo "Decrypted SOPS -> $out"; fi ;;
  esac
}

echo "== PMOVES .env Setup (bash) =="
[[ -f .env.example ]] || { echo ".env.example not found in pmoves/."; exit 1; }
[[ "$provider" != none ]] && pull_from_provider "$provider" || true

declare -A envmap
if [[ -f .env ]]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    k="${line%%=*}"; v="${line#*=}"
    envmap["$k"]="$v"
  done < .env
fi

added=0
while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  key="${line%%=*}"
  cur="${envmap[$key]:-}"
  if [[ -n "$cur" && $force -eq 0 ]]; then continue; fi
  def="${cur:-${!key:-}}"
  [[ -z "$def" ]] && def="$(suggest_default "$key")"
  val="$def"
  if [[ $yes -eq 0 ]]; then
    if is_secret "$key"; then
      read -r -s -p "Enter value for $key [hidden]" input; echo
      [[ -n "$input" ]] && val="$input"
    else
      if [[ -n "$def" ]]; then read -r -p "Enter value for $key [$def]: " input; else read -r -p "Enter value for $key: " input; fi
      [[ -n "$input" ]] && val="$input"
    fi
  fi
  printf "%s=%s\n" "$key" "$val" >> .env.tmp.$$ 
  added=$((added+1))
done < .env.example

if [[ $added -gt 0 ]]; then
  touch .env
  printf "\n# --- Added by env_setup to align with .env.example (local dev defaults) ---\n" >> .env
  cat .env.tmp.$$ >> .env
  rm -f .env.tmp.$$
  echo "Updated .env with $added keys."
else
  rm -f .env.tmp.$$ 2>/dev/null || true
  echo "Nothing to add; .env already covers .env.example keys."
fi

echo "Running preflight check..."
pwsh -NoProfile -File scripts/env_check.ps1 -Quick 2>/dev/null || bash scripts/env_check.sh -q || true

echo "Done."

