#!/usr/bin/env bash
# jellyfin_backup.sh - Jellyfin 10.11 backup/restore helper for PMOVES provisioning bundles
set -u
set -o pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR=$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)
STACK_ROOT_DEFAULT=$(cd "${SCRIPT_DIR}/.." && pwd)
STACK_ROOT=${JELLYFIN_STACK_ROOT:-${STACK_ROOT_DEFAULT}}
ARCHIVE_DIR_DEFAULT="${STACK_ROOT}/backups"
ARCHIVE_DIR="${JELLYFIN_ARCHIVE_DIR:-${ARCHIVE_DIR_DEFAULT}}"
JELLYFIN_URL=${JELLYFIN_URL:-"http://localhost:8096"}
CURL_BIN=${CURL_BIN:-curl}
JQ_BIN=${JQ_BIN:-jq}
UPLOAD_TO_SUPABASE=1
SUPABASE_BUCKET=${SUPABASE_JELLYFIN_BACKUP_BUCKET:-"jellyfin-backups"}
SUPABASE_PREFIX=${SUPABASE_JELLYFIN_BACKUP_PREFIX:-"archives"}
BACKUP_PAYLOAD='{"Metadata":true,"Trickplay":true,"Subtitles":true,"Database":true}'
AUTH_TOKEN=""
CLIENT_HEADER="MediaBrowser Client=\"pmoves-backup\", Device=\"PMOVES Provisioning\", DeviceId=\"pmoves-provisioning\", Version=\"1.0.0\""
JELLYFIN_CONFIG_PATH=${JELLYFIN_CONFIG_PATH:-"${STACK_ROOT}/jellyfin/config"}
JELLYFIN_CACHE_PATH=${JELLYFIN_CACHE_PATH:-"${STACK_ROOT}/jellyfin/cache"}

log() {
  echo "[jellyfin-backup] $*" >&2
}

warn() {
  log "WARN: $*"
}

err() {
  log "ERROR: $*" >&2
}

usage() {
  cat <<USAGE
Usage: ${0##*/} <command> [options]

Commands:
  backup            Trigger a Jellyfin backup, copy the archive into the provisioning bundle, and optionally upload to Supabase.
  restore           Copy an archive into Jellyfin's backup directory and invoke the restore endpoint.

Options (apply to both commands):
  --stack-root PATH       Override the Jellyfin stack root (default: ${STACK_ROOT_DEFAULT}).
  --bundle-dir PATH       Override the archive output directory (default: <stack-root>/backups).
  --config-dir PATH       Override host path mapped to /config (default: <stack-root>/jellyfin/config).
  --cache-dir PATH        Override host path mapped to /cache (default: <stack-root>/jellyfin/cache).
  --supabase-bucket NAME  Override Supabase bucket (default: ${SUPABASE_BUCKET}).
  --supabase-prefix PATH  Override Supabase prefix (default: ${SUPABASE_PREFIX}).
  --no-upload             Skip Supabase upload even if secrets are present.
  -h, --help              Show this help message.

Restore command options:
  --archive PATH          Archive to restore (local path inside provisioning bundle).

Environment fallbacks:
  JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USERNAME, JELLYFIN_PASSWORD,
  SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_JELLYFIN_BACKUP_BUCKET,
  SUPABASE_JELLYFIN_BACKUP_PREFIX, JELLYFIN_STACK_ROOT, JELLYFIN_ARCHIVE_DIR,
  JELLYFIN_CONFIG_PATH, JELLYFIN_CACHE_PATH.
USAGE
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command '$1' not found in PATH."
    exit 1
  fi
}

sanitize_bucket_path() {
  local value="$1"
  value="${value#/}"
  echo "${value%/}"
}

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      local key="${line%%=*}"
      local value="${line#*=}"
      value="${value%$'\r'}"
      value="${value#\"}"
      value="${value%\"}"
      value="${value#\'}"
      value="${value%\'}"
      export "$key=$value"
    fi
  done < "$file"
}

load_stack_env() {
  local root="$1"
  load_env_file "${root}/.env"
  load_env_file "${root}/.env.local"
}

resolve_host_path() {
  local candidate="$1"
  if [[ -f "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi
  if [[ "$candidate" == /config/* ]]; then
    local suffix="${candidate#/config/}"
    local host_path="${JELLYFIN_CONFIG_PATH}/${suffix}"
    if [[ -f "$host_path" ]]; then
      echo "$host_path"
      return 0
    fi
  fi
  if [[ "$candidate" == /cache/* ]]; then
    local suffix="${candidate#/cache/}"
    local host_path="${JELLYFIN_CACHE_PATH}/${suffix}"
    if [[ -f "$host_path" ]]; then
      echo "$host_path"
      return 0
    fi
  fi
  echo "$candidate"
}

jellyfin_ping() {
  ${CURL_BIN} -sS --max-time 5 "${JELLYFIN_URL%/}/System/Ping" >/dev/null
}

get_auth_token() {
  if [[ -n "${JELLYFIN_API_KEY:-}" ]]; then
    AUTH_TOKEN="${JELLYFIN_API_KEY}"
    return 0
  fi
  if [[ -n "${JELLYFIN_USERNAME:-}" && -n "${JELLYFIN_PASSWORD:-}" ]]; then
    local response
    response=$(${CURL_BIN} -sS --fail \
      -H "Content-Type: application/json" \
      -H "X-Emby-Authorization: ${CLIENT_HEADER}" \
      -X POST "${JELLYFIN_URL%/}/Users/AuthenticateByName" \
      -d "{\"Username\":\"${JELLYFIN_USERNAME}\",\"Pw\":\"${JELLYFIN_PASSWORD}\"}" 2>/dev/null) || return 1
    AUTH_TOKEN=$(printf '%s' "$response" | ${JQ_BIN} -r '.AccessToken' 2>/dev/null)
    if [[ -n "$AUTH_TOKEN" && "$AUTH_TOKEN" != null ]]; then
      return 0
    fi
  fi
  return 1
}

call_jellyfin_api() {
  local method="$1"
  local path="$2"
  shift 2
  local headers=("-H" "X-Emby-Authorization: ${CLIENT_HEADER}")
  if [[ -n "$AUTH_TOKEN" ]]; then
    headers+=("-H" "X-Emby-Token: ${AUTH_TOKEN}")
  fi
  ${CURL_BIN} -sS --fail -X "$method" "${JELLYFIN_URL%/}${path}" "${headers[@]}" "$@"
}

perform_backup() {
  if ! jellyfin_ping; then
    warn "Jellyfin is unreachable at ${JELLYFIN_URL}; skipping backup."
    return 0
  fi
  if ! get_auth_token; then
    warn "Unable to obtain Jellyfin token (set JELLYFIN_API_KEY or username/password)."
    return 1
  fi
  local response
  response=$(call_jellyfin_api POST "/Backup/Create" -H "Content-Type: application/json" -d "${BACKUP_PAYLOAD}") || return 1
  local manifest_path
  manifest_path=$(printf '%s' "$response" | ${JQ_BIN} -r '.Path')
  if [[ -z "$manifest_path" || "$manifest_path" == null ]]; then
    err "Backup manifest did not include archive path."
    return 1
  fi
  local resolved
  resolved=$(resolve_host_path "$manifest_path")
  if [[ ! -f "$resolved" ]]; then
    err "Backup archive ${resolved} not found on host."
    return 1
  fi
  mkdir -p "$ARCHIVE_DIR"
  local archive_name
  archive_name=$(basename "$manifest_path")
  local dest="${ARCHIVE_DIR}/${archive_name}"
  cp "$resolved" "$dest"
  log "Backup stored at ${dest}."
  if (( UPLOAD_TO_SUPABASE )); then
    upload_to_supabase "$dest"
  else
    log "Supabase upload disabled (--no-upload)."
  fi
}

supabase_ready() {
  [[ -n "${SUPABASE_URL:-}" && -n "${SUPABASE_SERVICE_KEY:-}" ]]
}

upload_to_supabase() {
  local file="$1"
  if ! supabase_ready; then
    warn "Supabase secrets missing; skipping upload."
    return 0
  fi
  local bucket
  bucket=$(sanitize_bucket_path "${SUPABASE_BUCKET}")
  local prefix
  prefix=$(sanitize_bucket_path "${SUPABASE_PREFIX}")
  local object_name
  object_name=$(basename "$file")
  local storage_path
  if [[ -n "$prefix" ]]; then
    storage_path="${prefix}/${object_name}"
  else
    storage_path="$object_name"
  fi
  local url="${SUPABASE_URL%/}/storage/v1/object/${bucket}/${storage_path}"
  if ${CURL_BIN} -sS --fail -X POST "$url" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
      -H "apikey: ${SUPABASE_SERVICE_KEY}" \
      -H "Content-Type: application/zip" \
      -H "x-upsert: true" \
      --data-binary @"${file}" >/dev/null; then
    log "Uploaded ${object_name} to Supabase bucket ${bucket}/${storage_path}."
  else
    warn "Failed to upload ${object_name} to Supabase."
    return 1
  fi
}

perform_restore() {
  local archive="$1"
  if [[ -z "$archive" ]]; then
    err "Restore requires --archive <path>."
    return 1
  fi
  if [[ ! -f "$archive" ]]; then
    err "Archive ${archive} not found."
    return 1
  fi
  if ! jellyfin_ping; then
    err "Jellyfin is unreachable at ${JELLYFIN_URL}; cannot restore."
    return 1
  fi
  if ! get_auth_token; then
    err "Unable to obtain Jellyfin token for restore."
    return 1
  fi
  local existing_list
  existing_list=$(call_jellyfin_api GET "/Backup" || true)
  local target_dir=""
  if [[ -n "$existing_list" ]]; then
    target_dir=$(printf '%s' "$existing_list" | ${JQ_BIN} -r '.[0].Path | select(.!=null) | split("/")[:-1] | join("/")')
  fi
  if [[ -z "$target_dir" ]]; then
    target_dir="${JELLYFIN_CONFIG_PATH}/data/backups"
    [[ -d "$target_dir" ]] || target_dir="${JELLYFIN_CONFIG_PATH}/backups"
  fi
  mkdir -p "$target_dir"
  local filename
  filename=$(basename "$archive")
  cp "$archive" "${target_dir}/${filename}"
  log "Copied ${archive} into ${target_dir}."
  if call_jellyfin_api POST "/Backup/Restore" -H "Content-Type: application/json" -d "{\"ArchiveFileName\":\"${filename}\"}" >/dev/null; then
    log "Restore scheduled for ${filename}. Jellyfin will restart to apply backup."
  else
    err "Failed to invoke restore endpoint."
    return 1
  fi
}

COMMAND=""
ARCHIVE_ARG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    backup|restore)
      COMMAND="$1"
      shift
      break
      ;;
    --stack-root)
      STACK_ROOT="$2"
      shift 2
      ;;
    --bundle-dir)
      ARCHIVE_DIR="$2"
      shift 2
      ;;
    --config-dir)
      JELLYFIN_CONFIG_PATH="$2"
      shift 2
      ;;
    --cache-dir)
      JELLYFIN_CACHE_PATH="$2"
      shift 2
      ;;
    --supabase-bucket)
      SUPABASE_BUCKET="$2"
      shift 2
      ;;
    --supabase-prefix)
      SUPABASE_PREFIX="$2"
      shift 2
      ;;
    --no-upload)
      UPLOAD_TO_SUPABASE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$COMMAND" ]]; then
  usage
  exit 1
fi

case "$COMMAND" in
  backup)
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --stack-root)
          STACK_ROOT="$2"; shift 2 ;;
        --bundle-dir)
          ARCHIVE_DIR="$2"; shift 2 ;;
        --config-dir)
          JELLYFIN_CONFIG_PATH="$2"; shift 2 ;;
        --cache-dir)
          JELLYFIN_CACHE_PATH="$2"; shift 2 ;;
        --supabase-bucket)
          SUPABASE_BUCKET="$2"; shift 2 ;;
        --supabase-prefix)
          SUPABASE_PREFIX="$2"; shift 2 ;;
        --no-upload)
          UPLOAD_TO_SUPABASE=0; shift ;;
        -h|--help)
          usage; exit 0 ;;
        *)
          err "Unknown option for backup: $1"
          usage
          exit 1
          ;;
      esac
    done
    ;;
  restore)
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --archive)
          ARCHIVE_ARG="$2"; shift 2 ;;
        --stack-root)
          STACK_ROOT="$2"; shift 2 ;;
        --bundle-dir)
          ARCHIVE_DIR="$2"; shift 2 ;;
        --config-dir)
          JELLYFIN_CONFIG_PATH="$2"; shift 2 ;;
        --cache-dir)
          JELLYFIN_CACHE_PATH="$2"; shift 2 ;;
        --supabase-bucket)
          SUPABASE_BUCKET="$2"; shift 2 ;;
        --supabase-prefix)
          SUPABASE_PREFIX="$2"; shift 2 ;;
        --no-upload)
          UPLOAD_TO_SUPABASE=0; shift ;;
        -h|--help)
          usage; exit 0 ;;
        *)
          err "Unknown option for restore: $1"
          usage
          exit 1
          ;;
      esac
    done
    ;;
esac

require_command "$CURL_BIN"
require_command "$JQ_BIN"
mkdir -p "$ARCHIVE_DIR"
load_stack_env "$STACK_ROOT"
SUPABASE_BUCKET=$(sanitize_bucket_path "$SUPABASE_BUCKET")
SUPABASE_PREFIX=$(sanitize_bucket_path "$SUPABASE_PREFIX")

case "$COMMAND" in
  backup)
    perform_backup
    ;;
  restore)
    perform_restore "$ARCHIVE_ARG"
    ;;
esac
