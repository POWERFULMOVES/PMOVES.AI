#!/usr/bin/env bash
# persona-session-hook.sh — SessionStart/Stop hook for persona consumption events.
#
# Publishes a persona.consumption.recorded.v1 event (kind=generic,
# item=session:<start|stop>) so agent harness sessions are first-class
# third-ref consumption signal alongside the Jellyfin human-side producer.
#
# Fail-soft by design: a missing agent id or an unreachable bus logs to
# stderr and exits 0. Never block a session on grounding telemetry.
#
# Env:
#   PMOVES_AGENT_ID   agent identity (required to emit; skip silently if unset)
#   PERSONA_HOOK_OFF  set to any value to disable
#   NATS_URL          bus url (defaults resolved by persona_consumption.py)

set -o pipefail 2>/dev/null || true

INPUT="$(cat 2>/dev/null)" || INPUT=""

[ -n "${PERSONA_HOOK_OFF:-}" ] && exit 0
AGENT="${PMOVES_AGENT_ID:-}"
if [ -z "$AGENT" ]; then
    echo "[persona-hook] PMOVES_AGENT_ID unset — skipping consumption event" >&2
    exit 0
fi

HOOK_EVENT="${PMOVES_PERSONA_HOOK_EVENT:-start}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Resolve NATS_URL from env.shared if not exported (host-side sessions).
# env.shared carries the Docker-internal hostname `nats`; from the host the
# broker is published on localhost:4222, so rewrite the host in the fallback.
if [ -z "${NATS_URL:-}" ]; then
    NATS_URL="$(sed -n 's/^NATS_URL=//p' "$ROOT/pmoves/env.shared" 2>/dev/null | tail -1 | tr -d '\r' | sed 's/@nats:/@localhost:/')" || NATS_URL=""
    [ -n "$NATS_URL" ] || NATS_URL="nats://localhost:4222"
    export NATS_URL
fi

PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "[persona-hook] no python3" >&2; exit 0; }

SESSION_ID="$(printf '%s' "$INPUT" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
SESSION_ARG=()
[ -n "$SESSION_ID" ] && SESSION_ARG=(--session "$SESSION_ID")

if ( cd "$ROOT" && "$PY" -m pmoves.tools.persona_consumption \
        --agent "$AGENT" --kind generic \
        --item "session:$HOOK_EVENT" \
        --domains agent-session,third-ref \
        "${SESSION_ARG[@]}" ) >/dev/null 2>&1; then
    echo "[persona-hook] consumption event published (session:$HOOK_EVENT, agent:$AGENT)" >&2
else
    echo "[persona-hook] publish failed (agent:$AGENT) — bus down or env missing; continuing" >&2
fi
exit 0
