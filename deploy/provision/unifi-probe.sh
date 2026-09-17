#!/usr/bin/env bash
# unifi-probe.sh — Query Unifi Network Application and cross-check host NICs
#
# Emits a unifi_topology JSON block for appending to glances-autodetect.sh output.
# Called automatically by glances-autodetect.sh when UNIFI_CONTROLLER_URL and
# UNIFI_API_KEY are set. Can also be run standalone.
#
# USAGE:
#   unifi-probe.sh [--json] [--controller URL] [--api-key KEY] [--site SITE]
#
# ENV VARS (used if flags omitted):
#   UNIFI_CONTROLLER_URL  e.g. https://unifi-controller or https://unifi-controller:8443
#   UNIFI_API_KEY         API key from: Unifi Network App → Settings → System → API
#   UNIFI_SITE            Site name (default: "default")
#
# OUTPUT (stdout, JSON):
#   Healthy:
#   {
#     "controller_url": "https://unifi-controller",
#     "site": "default",
#     "api_version": "modern" | "legacy",
#     "managed_devices": [
#       { "mac": "aa:bb:cc:dd:ee:ff", "hostname": "...", "ip": "<device-ip>",
#         "vlan": 10, "port": 3, "uplink_mbps": 1000, "type": "switch|ap|gw|client" }
#     ],
#     "host_mac_matches": [
#       { "nic": "eth0", "mac": "aa:bb:cc:dd:ee:ff", "status": "matched|unmanaged" }
#     ],
#     "ghost_devices": [
#       { "mac": "aa:bb:cc:dd:ee:ff", "hostname": "...", "note": "seen by Unifi, not on this host" }
#     ],
#     "vlan_mismatches": [
#       { "nic": "eth0", "host_vlan": 0, "unifi_vlan": 10 }
#     ],
#     "topology_ok": true,
#     "error": null
#   }
#
#   Skipped (env vars absent):
#   { "skipped": true, "reason": "UNIFI_CONTROLLER_URL not set" }
#
#   Unreachable / auth failure:
#   { "controller_url": "...", "topology_ok": false, "error": "unreachable|auth_failed|jq_missing" }
#
# SAFETY:
#   - Never exits non-zero due to controller issues (best-effort enrichment)
#   - Self-signed certs accepted (-k / -SkipCertificateCheck)
#   - No state written; read-only queries only

set -euo pipefail

# --- Arg parsing ---
CONTROLLER_URL="${UNIFI_CONTROLLER_URL:-}"
API_KEY="${UNIFI_API_KEY:-}"
SITE="${UNIFI_SITE:-default}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)           shift ;;  # no-op: script always emits JSON
    --controller)     CONTROLLER_URL="$2"; shift 2 ;;
    --api-key)        API_KEY="$2"; shift 2 ;;
    --site)           SITE="$2"; shift 2 ;;
    --help|-h)
      sed -n '2,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *)                printf '{"skipped":true,"reason":"unknown_arg: %s"}\n' "$1"; exit 0 ;;
  esac
done

# --- Safe JSON output (never fails the caller) ---
emit_skip() {
  printf '{"skipped":true,"reason":"%s"}\n' "$1"
  exit 0
}

emit_error() {
  local url="${CONTROLLER_URL:-null}"
  if [[ "$url" != "null" ]]; then url="\"${url}\""; fi
  printf '{"controller_url":%s,"topology_ok":false,"error":"%s"}\n' "$url" "$1"
  exit 0
}

# --- Pre-flight: jq required ---
if ! command -v jq > /dev/null 2>&1; then
  emit_error "jq_missing"
fi

# --- Pre-flight: curl required ---
if ! command -v curl > /dev/null 2>&1; then
  emit_error "curl_missing"
fi

# --- Skip if not configured ---
[[ -z "$CONTROLLER_URL" ]] && emit_skip "UNIFI_CONTROLLER_URL not set"
[[ -z "$API_KEY" ]]         && emit_skip "UNIFI_API_KEY not set"

# Strip trailing slash
CONTROLLER_URL="${CONTROLLER_URL%/}"

# --- Normalize MAC to lowercase colon form ---
normalize_mac() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/-/:/g'
}

# --- Collect host MACs (from ip link) ---
HOST_MACS=()
while IFS= read -r mac; do
  [[ "$mac" == "00:00:00:00:00:00" ]] && continue
  HOST_MACS+=("$(normalize_mac "$mac")")
done < <(ip link show 2>/dev/null | grep -i "link/ether" | awk '{print $2}')

# Map mac → nic name for cross-check
declare -A MAC_TO_NIC
current_iface=""
while IFS= read -r line; do
  if echo "$line" | grep -qE '^[0-9]+:'; then
    current_iface=$(echo "$line" | awk -F': ' '{print $2}' | awk '{print $1}')
  elif echo "$line" | grep -qi "link/ether"; then
    mac=$(echo "$line" | awk '{print $2}')
    nmac=$(normalize_mac "$mac")
    [[ "$nmac" != "00:00:00:00:00:00" ]] && MAC_TO_NIC["$nmac"]="$current_iface"
  fi
done < <(ip link show 2>/dev/null)

# --- Detect API version: try modern UDM path first, fall back to legacy ---
API_VERSION="unknown"
CURL_OPTS=(-sk -H "X-API-KEY: ${API_KEY}" -H "Content-Type: application/json" --max-time 8)

# Modern: /proxy/network/api/s/{site}/stat/sta (UDM/UDM Pro/CloudKey Gen2+)
MODERN_URL="${CONTROLLER_URL}/proxy/network/api/s/${SITE}/stat/sta"
LEGACY_URL="${CONTROLLER_URL}/api/s/${SITE}/stat/sta"

HTTP_CODE=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" "$MODERN_URL" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
  API_VERSION="modern"
  BASE_URL="${CONTROLLER_URL}/proxy/network/api/s/${SITE}"
elif [[ "$HTTP_CODE" == "401" || "$HTTP_CODE" == "403" ]]; then
  emit_error "auth_failed"
elif [[ "$HTTP_CODE" == "000" ]]; then
  emit_error "unreachable"
else
  # Try legacy path
  HTTP_CODE_L=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" "$LEGACY_URL" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE_L" == "200" ]]; then
    API_VERSION="legacy"
    BASE_URL="${CONTROLLER_URL}/api/s/${SITE}"
  elif [[ "$HTTP_CODE_L" == "401" || "$HTTP_CODE_L" == "403" ]]; then
    emit_error "auth_failed"
  else
    emit_error "unreachable"
  fi
fi

# --- Fetch managed devices (switches, APs, gateways) ---
DEVICES_RAW=$(curl "${CURL_OPTS[@]}" "${BASE_URL}/stat/device" 2>/dev/null || echo '{"data":[]}')
CLIENTS_RAW=$(curl "${CURL_OPTS[@]}" "${BASE_URL}/stat/sta"    2>/dev/null || echo '{"data":[]}')

# --- Build managed_devices array (devices + clients merged by MAC) ---
# Devices: switches/APs/gateways
DEVICE_MACS_JSON=$(echo "$DEVICES_RAW" | jq -c '
  [.data[] |
    {
      mac:        (.mac // "" | ascii_downcase | gsub("-"; ":")),
      hostname:   (.name // .hostname // ""),
      ip:         (.ip // ""),
      vlan:       (.vlan // 0),
      port:       (.uplink.port_idx // 0),
      uplink_mbps: (.uplink.speed // 0),
      type:       (if .type == "usw" then "switch"
                   elif .type == "uap" then "ap"
                   elif .type == "ugw" or .type == "udm" then "gw"
                   else (.type // "device") end)
    }
  ]' 2>/dev/null || echo '[]')

# Clients: connected stations (enriches with client MACs from the controller)
CLIENT_MACS_JSON=$(echo "$CLIENTS_RAW" | jq -c '
  [.data[] |
    {
      mac:        (.mac // "" | ascii_downcase | gsub("-"; ":")),
      hostname:   (.hostname // .name // ""),
      ip:         (.ip // ""),
      vlan:       (.vlan // 0),
      port:       0,
      uplink_mbps: (.uplink_speed // 0),
      type:       "client"
    }
  ]' 2>/dev/null || echo '[]')

# Merge (devices take precedence over clients for the same MAC)
MANAGED_DEVICES_JSON=$(jq -sc '
  (.[0] + .[1]) |
  group_by(.mac) |
  map(if length > 1 then .[0] else .[0] end)
' <(echo "$DEVICE_MACS_JSON") <(echo "$CLIENT_MACS_JSON") 2>/dev/null || echo '[]')

# Extract all Unifi-known MACs as a flat array (normalized)
UNIFI_MACS=$(echo "$MANAGED_DEVICES_JSON" | jq -r '.[].mac' 2>/dev/null || true)

# --- Cross-check: host MACs vs Unifi ---
HOST_MAC_MATCHES=()
for mac in "${HOST_MACS[@]}"; do
  nic="${MAC_TO_NIC[$mac]:-unknown}"
  if echo "$UNIFI_MACS" | grep -qx "$mac"; then
    status="matched"
  else
    status="unmanaged"
  fi
  HOST_MAC_MATCHES+=("$(jq -nc --arg nic "$nic" --arg mac "$mac" --arg status "$status" \
    '{nic:$nic,mac:$mac,status:$status}')")
done
HOST_MAC_MATCHES_JSON="[$(IFS=','; echo "${HOST_MAC_MATCHES[*]}")]"
[ "${#HOST_MAC_MATCHES[@]}" -eq 0 ] && HOST_MAC_MATCHES_JSON="[]"

# --- Ghost devices: Unifi sees them but host doesn't claim them ---
GHOST_DEVICES=()
HOST_MAC_LIST=$(printf '%s\n' "${HOST_MACS[@]}")
while IFS= read -r unic_mac; do
  [[ -z "$unic_mac" ]] && continue
  if ! echo "$HOST_MAC_LIST" | grep -qx "$unic_mac"; then
    hostname=$(echo "$MANAGED_DEVICES_JSON" | \
      jq -r --arg m "$unic_mac" '.[] | select(.mac == $m) | .hostname' 2>/dev/null || echo "")
    GHOST_DEVICES+=("$(jq -nc --arg mac "$unic_mac" --arg hostname "$hostname" \
      '{mac:$mac,hostname:$hostname,note:"seen by Unifi, not on this host"}')")
  fi
done <<< "$UNIFI_MACS"
GHOST_DEVICES_JSON="[$(IFS=','; echo "${GHOST_DEVICES[*]}")]"
[ "${#GHOST_DEVICES[@]}" -eq 0 ] && GHOST_DEVICES_JSON="[]"

# --- VLAN mismatches ---
# Host VLAN is determined from the NIC's tagged interface (e.g. eth0.10 = VLAN 10)
# We check each matched NIC's expected VLAN from Unifi vs what the host reports
VLAN_MISMATCH_ENTRIES=()
for mac in "${HOST_MACS[@]}"; do
  nic="${MAC_TO_NIC[$mac]:-unknown}"
  unifi_vlan=$(echo "$MANAGED_DEVICES_JSON" | \
    jq -r --arg m "$mac" '.[] | select(.mac == $m) | .vlan' 2>/dev/null || echo "0")
  unifi_vlan="${unifi_vlan:-0}"
  if [[ "$unifi_vlan" != "0" && "$unifi_vlan" != "null" ]]; then
    # Check if host has a tagged sub-interface for this VLAN
    if ! ip link show 2>/dev/null | grep -qE "^[0-9]+: ${nic}\\.${unifi_vlan}"; then
      VLAN_MISMATCH_ENTRIES+=("$(jq -nc --arg nic "$nic" --argjson uv "$unifi_vlan" \
        '{nic:$nic,host_vlan:0,unifi_vlan:$uv}')")
    fi
  fi
done
TMPVLAN="[$(IFS=','; echo "${VLAN_MISMATCH_ENTRIES[*]}")]"
[ "${#VLAN_MISMATCH_ENTRIES[@]}" -eq 0 ] && TMPVLAN="[]"
VLAN_MISMATCHES_JSON="$TMPVLAN"

# --- topology_ok: true if at least one matched and no ghosts ---
GHOST_COUNT=$(echo "$GHOST_DEVICES_JSON" | jq 'length' 2>/dev/null || echo "0")
MATCH_COUNT=$(echo "$HOST_MAC_MATCHES_JSON" | \
  jq '[.[] | select(.status == "matched")] | length' 2>/dev/null || echo "0")

if [[ "$GHOST_COUNT" -eq 0 && "$MATCH_COUNT" -gt 0 ]]; then
  TOPOLOGY_OK="true"
else
  TOPOLOGY_OK="false"
fi

# --- Emit final JSON ---
jq -n \
  --arg controller_url "$CONTROLLER_URL" \
  --arg site "$SITE" \
  --arg api_version "$API_VERSION" \
  --argjson managed_devices "$MANAGED_DEVICES_JSON" \
  --argjson host_mac_matches "$HOST_MAC_MATCHES_JSON" \
  --argjson ghost_devices "$GHOST_DEVICES_JSON" \
  --argjson vlan_mismatches "$VLAN_MISMATCHES_JSON" \
  --argjson topology_ok "$TOPOLOGY_OK" \
  '{
    controller_url:   $controller_url,
    site:             $site,
    api_version:      $api_version,
    managed_devices:  $managed_devices,
    host_mac_matches: $host_mac_matches,
    ghost_devices:    $ghost_devices,
    vlan_mismatches:  $vlan_mismatches,
    topology_ok:      $topology_ok,
    error:            null
  }'
