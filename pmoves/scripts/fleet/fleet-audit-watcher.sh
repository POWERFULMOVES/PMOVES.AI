#!/usr/bin/env bash
# =============================================================================
# PMOVES Fleet Audit Watcher
#
# Runs on KVM2 as a systemd service. Tails hbbs/hbbr journals for connection
# events and publishes them to NATS for fleet-wide observability.
#
# Install:
#   scp fleet-audit-watcher.sh root@<KVM2>:/opt/pmoves/
#   scp fleet-audit-watcher.service root@<KVM2>:/etc/systemd/system/
#   ssh root@<KVM2> "systemctl daemon-reload && systemctl enable --now fleet-audit-watcher"
#
# NATS subjects published:
#   fleet.device.registered.v1   — new client registered (update_pk)
#   fleet.audit.connection.v1    — relay connection event
#   fleet.audit.heartbeat.v1     — watcher alive (every 5 minutes)
#
# Dependencies: nats CLI (https://github.com/nats-io/natscli)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NATS_URL="${NATS_URL:-nats://nats:pmoves@nats:4222}"
LOG_DIR="/var/log/pmoves"
LOG_FILE="${LOG_DIR}/fleet-audit.jsonl"
HEARTBEAT_INTERVAL=300  # 5 minutes

mkdir -p "${LOG_DIR}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ts() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

publish() {
    local subject="$1"
    local payload="$2"

    # Append to local log
    echo "${payload}" >> "${LOG_FILE}"

    # Publish to NATS (fire-and-forget, don't block on failure)
    if command -v nats &>/dev/null; then
        echo "${payload}" | nats pub "${subject}" --server "${NATS_URL}" 2>/dev/null || true
    fi
}

# ---------------------------------------------------------------------------
# Heartbeat (background)
# ---------------------------------------------------------------------------

heartbeat_loop() {
    while true; do
        local payload
        payload=$(cat <<EOF
{"event":"heartbeat","ts":"$(ts)","service":"fleet-audit-watcher","node":"kvm2"}
EOF
        )
        publish "fleet.audit.heartbeat.v1" "${payload}"
        sleep "${HEARTBEAT_INTERVAL}"
    done
}

heartbeat_loop &
HEARTBEAT_PID=$!
trap "kill ${HEARTBEAT_PID} 2>/dev/null" EXIT

# ---------------------------------------------------------------------------
# Watch hbbs journal for registration + connection events
# ---------------------------------------------------------------------------

echo "[$(ts)] Fleet audit watcher started on KVM2"
echo "[$(ts)] NATS: ${NATS_URL}"
echo "[$(ts)] Log: ${LOG_FILE}"

journalctl -u hbbs -u hbbr -f --no-pager --output=short-iso 2>/dev/null | while IFS= read -r line; do

    # New client registration (update_pk)
    if echo "${line}" | grep -q "update_pk"; then
        # Extract client ID from log line (format varies, best-effort)
        client_id=$(echo "${line}" | grep -oP 'update_pk \K[^ ]+' || echo "unknown")
        payload=$(cat <<EOF
{"event":"device.registered","ts":"$(ts)","client_id":"${client_id}","raw":"${line}"}
EOF
        )
        echo "[$(ts)] NEW REGISTRATION: ${client_id}"
        publish "fleet.device.registered.v1" "${payload}"
    fi

    # Relay connection events
    if echo "${line}" | grep -qE "(relay connection|new relay)"; then
        payload=$(cat <<EOF
{"event":"relay.connection","ts":"$(ts)","raw":"${line}"}
EOF
        )
        publish "fleet.audit.connection.v1" "${payload}"
    fi

    # Connection closed / disconnected
    if echo "${line}" | grep -qiE "(closed|disconnect|timeout)"; then
        payload=$(cat <<EOF
{"event":"connection.closed","ts":"$(ts)","raw":"${line}"}
EOF
        )
        publish "fleet.audit.connection.v1" "${payload}"
    fi

done
