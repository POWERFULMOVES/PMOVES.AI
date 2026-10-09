#!/usr/bin/env bash
# run_smoke.sh — Tier 2 smoke validation for Wave 0 governance + format hooks.
#
# Each test:
#   1. Sets up hermetic tmp dir with required fixture files.
#   2. Pipes a JSON payload (matching Claude Code's hook stdin contract) into
#      the hook script.
#   3. Asserts the exit code matches expected.
#
# NO live services required. Runs in CI.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
FAILURES=()

ok()   { echo "  ✅ $*"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $*"; FAIL=$((FAIL+1)); FAILURES+=("$*"); }

run_case() {
  # Args: <case-name> <expected-exit> <hook-cmd> [stdin-json]
  local name="$1" expected="$2" hook_cmd="$3" stdin="${4:-}"
  local actual
  if [[ -n "$stdin" ]]; then
    actual=$(printf '%s' "$stdin" | eval "$hook_cmd" 2>/dev/null; echo "EXIT:$?")
  else
    actual=$(eval "$hook_cmd" 2>/dev/null; echo "EXIT:$?")
  fi
  local code="${actual##*EXIT:}"
  if [[ "$code" == "$expected" ]]; then
    ok "$name (exit=$code)"
  else
    bad "$name (expected exit=$expected, got $code)"
  fi
}

section() { echo; echo "── $* ──"; }

# ═══════════════════════════════════════════════════════════════════════
# Hook 1: known-roads-enforcer.py — easiest, no filesystem deps
# ═══════════════════════════════════════════════════════════════════════
section "known-roads-enforcer.py"

HOOK1=".claude/hooks/governance/known-roads-enforcer.py"

run_case "raw docker compose up → BLOCK" 2 "python3 $HOOK1" \
  '{"tool_name":"Bash","tool_input":{"command":"docker compose up -d"}}'

run_case "raw docker compose restart → BLOCK" 2 "python3 $HOOK1" \
  '{"tool_name":"Bash","tool_input":{"command":"docker compose restart api"}}'

run_case "raw docker compose down → BLOCK" 2 "python3 $HOOK1" \
  '{"tool_name":"Bash","tool_input":{"command":"docker compose down -v"}}'

run_case "make -C pmoves up-dev → ALLOW" 0 "python3 $HOOK1" \
  '{"tool_name":"Bash","tool_input":{"command":"make -C pmoves up-dev"}}'

run_case "unrelated bash → ALLOW" 0 "python3 $HOOK1" \
  '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'

run_case "non-Bash tool → ALLOW" 0 "python3 $HOOK1" \
  '{"tool_name":"Edit","tool_input":{"file_path":"foo.py"}}'

run_case "malformed stdin → ALLOW (defensive)" 0 "python3 $HOOK1" \
  'not json at all'

# ═══════════════════════════════════════════════════════════════════════
# Hook 2: claim-collision-pre.py — hermetic tmp register
# ═══════════════════════════════════════════════════════════════════════
section "claim-collision-pre.py"

HOOK2=".claude/hooks/governance/claim-collision-pre.py"

TMP2=$(mktemp -d)
trap "rm -rf $TMP2" EXIT
REGISTER="$TMP2/AGNOTE4482PHI.t1.md"
cat >"$REGISTER" <<'EOF'
# Active Claim Register

- `2026-05-01T10:00:00Z` CLAIM `EXISTING-OWNER-A` scope: testing. Branch `feat/held-lane`
- `2026-05-02T11:00:00Z` CLAIM `BOTH-OPEN-OWNER` scope: more testing. Branch `feat/released-lane`
- `2026-05-03T12:00:00Z` RELEASE `BOTH-OPEN-OWNER` scope: done.
EOF
# So: feat/held-lane is HELD by EXISTING-OWNER-A; feat/released-lane is FREE.
#
# These cases were rewritten 2026-08-25. They previously asserted the INVERTED
# rule -- "same owner re-claiming -> BLOCK" -- which is why the defect survived
# a green smoke suite: the test agreed with the bug. The gate is keyed on the
# LANE now, so a collision means ANOTHER owner already holds that branch.

# Collision: a DIFFERENT owner wants a lane that is held → BLOCK.
# This is the event the register exists to prevent; under the owner-keyed
# implementation it returned 0.
PAYLOAD2A=$(jq -nc --arg fp "$REGISTER" --arg ns "- new CLAIM \`OTHER-OWNER-B\` scope: same lane. Branch \`feat/held-lane\`" \
  '{tool_name:"Edit",tool_input:{file_path:$fp,new_string:$ns}}')
run_case "different owner takes a held lane → BLOCK" 2 "python3 $HOOK2" "$PAYLOAD2A"

# Same owner, DIFFERENT lane → ALLOW. A node running several lanes at once is
# the normal case here; blocking it was the false positive that made agents
# route around the gate.
PAYLOAD2B=$(jq -nc --arg fp "$REGISTER" --arg ns "- new CLAIM \`EXISTING-OWNER-A\` scope: unrelated. Branch \`docs/other-lane\`" \
  '{tool_name:"Edit",tool_input:{file_path:$fp,new_string:$ns}}')
run_case "same owner, different lane → ALLOW" 0 "python3 $HOOK2" "$PAYLOAD2B"

# Same owner re-naming its OWN held lane → ALLOW (not a collision with itself).
PAYLOAD2C=$(jq -nc --arg fp "$REGISTER" --arg ns "- new CLAIM \`EXISTING-OWNER-A\` scope: more of the same. Branch \`feat/held-lane\`" \
  '{tool_name:"Edit",tool_input:{file_path:$fp,new_string:$ns}}')
run_case "same owner re-names its own lane → ALLOW" 0 "python3 $HOOK2" "$PAYLOAD2C"

# A released lane is free for anyone → ALLOW.
PAYLOAD2D=$(jq -nc --arg fp "$REGISTER" --arg ns "- new CLAIM \`FRESH-OWNER\` scope: taking it over. Branch \`feat/released-lane\`" \
  '{tool_name:"Edit",tool_input:{file_path:$fp,new_string:$ns}}')
run_case "released lane is free → ALLOW" 0 "python3 $HOOK2" "$PAYLOAD2D"

# A claim naming no branch cannot be compared against anything, so it is
# REFUSED. This asserted ALLOW plus a "NOT CHECKED" line until 2026-09-02,
# which made the raw shell write more permissive than `register_append.py` --
# the sanctioned path refuses the identical row at exit 3. AGENTS.md requires
# a CLAIM to carry branch + scope + TTL, and could-not-measure is not a pass.
PAYLOAD2E=$(jq -nc --arg fp "$REGISTER" --arg ns "- new CLAIM \`FRESH-OWNER\` scope: freeform prose, no branch named" \
  '{tool_name:"Edit",tool_input:{file_path:$fp,new_string:$ns}}')
run_case "unkeyed claim → BLOCK" 2 "python3 $HOOK2" "$PAYLOAD2E"
# CAPTURED, NOT PIPED. `set -o pipefail` is on and the hook now exits 2, so
# `hook | grep -q` returns 2 however well the grep matched -- the assertion
# would report a missing message that is right there. Every stderr check
# below reads a variable.
OUT2E=$(python3 "$HOOK2" <<<"$PAYLOAD2E" 2>&1 >/dev/null || true)
case "$OUT2E" in
  *"names no branch"*) ok "unkeyed claim refusal names the missing lane" ;;
  *) bad "unkeyed claim refusal names the missing lane" ;;
esac
case "$OUT2E" in
  *"register-claim"*) ok "unkeyed claim refusal names the sanctioned path" ;;
  *) bad "unkeyed claim refusal names the sanctioned path" ;;
esac

# Non-register file → ALLOW
PAYLOAD2F=$(jq -nc --arg ns "- CLAIM \`whatever\` Branch \`feat/held-lane\`" \
  '{tool_name:"Edit",tool_input:{file_path:"/tmp/some-other.md",new_string:$ns}}')
run_case "non-register file → ALLOW" 0 "python3 $HOOK2" "$PAYLOAD2F"

# Write tool on register (no CLAIM) → ALLOW
PAYLOAD2G=$(jq -nc --arg fp "$REGISTER" --arg c "fresh content with no CLAIM" \
  '{tool_name:"Write",tool_input:{file_path:$fp,content:$c}}')
run_case "Write with no CLAIM → ALLOW" 0 "python3 $HOOK2" "$PAYLOAD2G"

# ═══════════════════════════════════════════════════════════════════════
# Hook 3: signoff-gate.sh — hermetic tmp checklist via CLAUDE_PROJECT_DIR
# ═══════════════════════════════════════════════════════════════════════
section "signoff-gate.sh"

HOOK3=".claude/hooks/governance/signoff-gate.sh"

# Set up a tmp project dir with a controlled checklist
TMP3=$(mktemp -d)
mkdir -p "$TMP3/pmoves/docs/AGENTS"
CHECKLIST="$TMP3/pmoves/docs/AGENTS/AGNOTE4482_SIGNOFF_CHECKLIST.md"
cat >"$CHECKLIST" <<'EOF'
# Sign-off Checklist

## PR #424242 — Test PR with all ACKs
[ACK: delivery] @claude-test
[ACK: control] @claude-test
[ACK: memory] @claude-test

## PR #555555 — Test PR missing memory
[ACK: delivery] @claude-test
[ACK: control] @claude-test
EOF

# All ACKs present → ALLOW
run_case "PR #424242 (all 3 ACKs) → ALLOW" 0 "CLAUDE_PROJECT_DIR=$TMP3 bash $HOOK3" \
  '{"tool_name":"Bash","tool_input":{"command":"gh pr merge 424242 --squash"}}'

# Missing memory ACK → BLOCK
run_case "PR #555555 (missing memory ACK) → BLOCK" 2 "CLAUDE_PROJECT_DIR=$TMP3 bash $HOOK3" \
  '{"tool_name":"Bash","tool_input":{"command":"gh pr merge 555555"}}'

# PR not in checklist → BLOCK
run_case "PR #999999 (not in checklist) → BLOCK" 2 "CLAUDE_PROJECT_DIR=$TMP3 bash $HOOK3" \
  '{"tool_name":"Bash","tool_input":{"command":"gh pr merge #999999"}}'

# No PR number → BLOCK
run_case "gh pr merge with no number → BLOCK" 2 "CLAUDE_PROJECT_DIR=$TMP3 bash $HOOK3" \
  '{"tool_name":"Bash","tool_input":{"command":"gh pr merge"}}'

# Non-merge command → ALLOW
run_case "gh pr view → ALLOW" 0 "CLAUDE_PROJECT_DIR=$TMP3 bash $HOOK3" \
  '{"tool_name":"Bash","tool_input":{"command":"gh pr view 424242"}}'

# Unrelated command → ALLOW
run_case "git status → ALLOW" 0 "CLAUDE_PROJECT_DIR=$TMP3 bash $HOOK3" \
  '{"tool_name":"Bash","tool_input":{"command":"git status"}}'

rm -rf "$TMP3"

# ═══════════════════════════════════════════════════════════════════════
# Hook 4 + 5: PostToolUse format hooks (must always exit 0)
# ═══════════════════════════════════════════════════════════════════════
section "PostToolUse format hooks (exit 0 always)"

HOOK4=".claude/hooks/posttool-format/python-format.sh"
HOOK5=".claude/hooks/posttool-format/ui-lint.sh"

run_case "python-format on .py → exit 0" 0 "bash $HOOK4" \
  '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/nonexistent.py"}}'

run_case "python-format on .md (skip) → exit 0" 0 "bash $HOOK4" \
  '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/readme.md"}}'

run_case "ui-lint on .ts outside ui/ → exit 0" 0 "bash $HOOK5" \
  '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/other.ts"}}'

run_case "ui-lint on .py → exit 0" 0 "bash $HOOK5" \
  '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/something.py"}}'

# ═══════════════════════════════════════════════════════════════════════
# Skill scripts — invoke without crashing
# ═══════════════════════════════════════════════════════════════════════
section "Skill scripts (smoke — no crash)"

# pmoves-submodule-fleet: read-only git ops; should exit 0 even with stale state
out=$(bash .claude/skills/pmoves-submodule-fleet/scripts/fleet_audit.sh 2>&1 | wc -l)
if [[ "$out" -gt 0 ]]; then ok "fleet_audit.sh produced $out lines"; else bad "fleet_audit.sh produced no output"; fi

# pmoves-mesh-preflight: expected non-zero (mesh down) — just check it runs
bash .claude/skills/pmoves-mesh-preflight/scripts/preflight.sh >/dev/null 2>&1
rc=$?
if [[ "$rc" -eq 0 || "$rc" -eq 1 ]]; then
  ok "preflight.sh exited cleanly (rc=$rc)"
else
  bad "preflight.sh crashed (rc=$rc)"
fi

# pmoves-nats-subject-audit: gated on the NATS monitoring port.
#
# This gate probed 8222 — the port INSIDE the container. Compose publishes it as
# `${NATS_MONITORING_PORT:-9223}:8222`, so on the host 8222 is closed and the
# gate skipped on every run, on every node, forever. A permanently-skipped case
# reports the same "⏸" whether NATS is down or the probe is simply pointed at
# the wrong port, so nothing ever surfaced it.
#
# Probe the same ports audit.py will try, in the same order, so the gate and the
# tool cannot disagree about whether NATS is reachable. 8222 stays in the list
# because docker-compose.z890.yml publishes `8222:8222`.
NATS_MON_PORT=""
for _p in "${NATS_MONITORING_PORT:-9223}" 8222; do
  if nc -z -w 1 127.0.0.1 "$_p" 2>/dev/null; then NATS_MON_PORT="$_p"; break; fi
done
if [[ -n "$NATS_MON_PORT" ]]; then
  python3 .claude/skills/pmoves-nats-subject-audit/scripts/audit.py >/dev/null 2>&1
  rc=$?
  if [[ "$rc" -le 1 ]]; then ok "audit.py ran (rc=$rc)"; else bad "audit.py crashed (rc=$rc)"; fi
else
  echo "  ⏸  audit.py SKIPPED (no NATS monitor on ${NATS_MONITORING_PORT:-9223} or 8222)"
fi

# pmoves-living-docs-refresh: wraps make target; just confirm it doesn't crash
bash .claude/skills/pmoves-living-docs-refresh/scripts/refresh.sh >/dev/null 2>&1
rc=$?
if [[ "$rc" -le 2 ]]; then ok "refresh.sh ran (rc=$rc)"; else bad "refresh.sh crashed (rc=$rc)"; fi

# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════"
echo "Smoke validation: PASS=$PASS  FAIL=$FAIL"
echo "════════════════════════════════════════════════════════"
if [[ "$FAIL" -ne 0 ]]; then
  echo "Failures:"
  for msg in "${FAILURES[@]}"; do echo "  - $msg"; done
  exit 1
fi
exit 0
