#!/usr/bin/env bash
# test-pm-cipher-token-bind.sh
# ---------------------------------------------------------------------------
# Guards pmoves/scripts/pm-cipher-token-bind.sh — the launcher fragment that
# binds a minted per-agent cipher token (CIPHER_TOKEN_<AGENT> from
# pmoves/.env.local) into the session env as CIPHER_API_TOKEN.
#
# The bug class this closes: a session told to declare agentId 'b850-claude'
# while the roster still carried the node bootstrap bearer — every declared-id
# call 403'd, every undeclared call filed under 'bootstrap'.
#
# Run: bash deploy/provision/tests/test-pm-cipher-token-bind.sh
# ---------------------------------------------------------------------------
set -uo pipefail

SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(CDPATH= cd -P -- "$SELF_DIR/../../.." && pwd)"
FRAGMENT="$REPO/pmoves/scripts/pm-cipher-token-bind.sh"

pass=0; fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

if [ ! -f "$FRAGMENT" ]; then
  printf '  FAIL  fragment missing: %s\n' "$FRAGMENT"
  exit 1
fi

FAKE_TOKEN="cipher_0123456789abcdef0123456789abcdef"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
mkdir -p "$FIXTURE/pmoves"
printf 'CIPHER_TOKEN_B850_CLAUDE=%s\n' "$FAKE_TOKEN" > "$FIXTURE/pmoves/.env.local"

run_bind() { # <agent> [pre-set CIPHER_API_TOKEN]
  (
    unset CIPHER_API_TOKEN PM_CARRY_BIND_LINE PM_CARRY_BIND_OK
    [ $# -ge 2 ] && export CIPHER_API_TOKEN="$2"
    . "$FRAGMENT"
    pm_cipher_token_bind "$FIXTURE" "$1"
    printf 'rc=%s\n' "$?"  >&2
    printf 'BINDLINE=%s\n' "${PM_CARRY_BIND_LINE:-}"
    printf 'OK=%s\n' "${PM_CARRY_BIND_OK:-}"
    printf 'ENV=%s\n' "${CIPHER_API_TOKEN:-}"
  ) 2>"$FIXTURE/stderr"
}

echo "== pm-cipher-token-bind =="

# --- 1. declared agent + key present -> binds --------------------------------
out="$(run_bind b850-claude)"
rc="$(sed -n 's/^rc=//p' "$FIXTURE/stderr" | head -1)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ "$envv" = "$FAKE_TOKEN" ] && ok "binds CIPHER_TOKEN_B850_CLAUDE into CIPHER_API_TOKEN" || bad "bind failed: got '${envv}'"
[ "$rc" = "0" ] && ok "returns 0 on bind" || bad "rc=$rc expected 0"
printf '%s\n' "$out" | grep -q 'OK=1' && ok "PM_CARRY_BIND_OK=1" || bad "PM_CARRY_BIND_OK not 1"
printf '%s\n' "$out" | grep -q 'bound for b850-claude' && ok "bind line names the agent" || bad "bind line missing agent"

# --- 2. the token must NEVER appear in the fragment's own output ------------
# (the ENV= line above is this test's own probe of the exported value; what
# must stay clean is the fragment's stderr and the PM_CARRY_BIND_LINE text)
if grep -qF "$FAKE_TOKEN" "$FIXTURE/stderr" || printf '%s\n' "$out" | sed -n 's/^BINDLINE=//p' | grep -qF "$FAKE_TOKEN"; then
  bad "token leaked into bind output"
else
  ok "token absent from bind line and stderr"
fi

# --- 3. no declared agent -> loud skip, no touch -----------------------------
out="$(run_bind "")"
rc="$(sed -n 's/^rc=//p' "$FIXTURE/stderr" | head -1)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ "$rc" = "1" ] && ok "returns 1 with no agentId" || bad "rc=$rc expected 1"
[ -z "$envv" ] && ok "env untouched with no agentId" || bad "env set with no agentId"
printf '%s\n' "$out" | grep -q 'no declared cipher agentId' && ok "skip reason is loud" || bad "skip reason missing"

# --- 4. key absent for the agent -> loud skip --------------------------------
out="$(run_bind z890-claude)"
rc="$(sed -n 's/^rc=//p' "$FIXTURE/stderr" | head -1)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ "$rc" = "1" ] && ok "returns 1 when key absent" || bad "rc=$rc expected 1"
[ -z "$envv" ] && ok "env untouched when key absent" || bad "env set when key absent"
printf '%s\n' "$out" | grep -q 'CIPHER_TOKEN_Z890_CLAUDE' && ok "names the exact key to add" || bad "missing key-name hint"

# --- 5. explicit per-agent env token wins ------------------------------------
out="$(run_bind b850-claude cipher_ffffffffffffffffffffffffffffffff)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ "$envv" = "cipher_ffffffffffffffffffffffffffffffff" ] && ok "explicit cipher_ env token respected" || bad "explicit token overridden"

# --- 6. non-cipher value under the key is refused ----------------------------
printf 'CIPHER_TOKEN_B850_CLAUDE=not-a-cipher-token\n' > "$FIXTURE/pmoves/.env.local"
out="$(run_bind b850-claude)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ -z "$envv" ] && ok "non cipher_-prefixed value refused" || bad "bound a non-cipher value"
printf '%s\n' "$out" | grep -q 'not a cipher_-prefixed token' && ok "refusal reason is loud" || bad "refusal reason missing"

# --- 7. key match is a FIXED string, not a regex ------------------------------
# agentId 'a.b-claude' -> key CIPHER_TOKEN_A.B_CLAUDE. Under the old
# `grep -E "^${key}="` the '.' matched any char, so CIPHER_TOKEN_AXB_CLAUDE
# (a different agent's token) was bound. Must be a loud miss instead.
printf 'CIPHER_TOKEN_AXB_CLAUDE=%s\n' "$FAKE_TOKEN" > "$FIXTURE/pmoves/.env.local"
out="$(run_bind a.b-claude)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ -z "$envv" ] && ok "regex metachar in agentId does not match another key" || bad "'.' in key matched CIPHER_TOKEN_AXB_CLAUDE"

# --- 8. a longer key sharing the prefix is not matched -----------------------
printf 'CIPHER_TOKEN_B850_CLAUDE_OLD=%s\n' "$FAKE_TOKEN" > "$FIXTURE/pmoves/.env.local"
out="$(run_bind b850-claude)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ -z "$envv" ] && ok "prefix-sharing key (_OLD) not matched" || bad "matched CIPHER_TOKEN_B850_CLAUDE_OLD"

# --- 9. trailing ' # comment' is stripped ------------------------------------
printf 'CIPHER_TOKEN_B850_CLAUDE=%s   # minted 2026-09-23\n' "$FAKE_TOKEN" > "$FIXTURE/pmoves/.env.local"
out="$(run_bind b850-claude)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ "$envv" = "$FAKE_TOKEN" ] && ok "trailing ' # comment' stripped" || bad "comment not stripped: got '${envv}'"

# --- 10. quoted value followed by a comment ----------------------------------
printf 'CIPHER_TOKEN_B850_CLAUDE="%s" # note\n' "$FAKE_TOKEN" > "$FIXTURE/pmoves/.env.local"
out="$(run_bind b850-claude)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ "$envv" = "$FAKE_TOKEN" ] && ok "quoted value + comment binds the bare token" || bad "quoted+comment: got '${envv}'"

# --- 11. malformed value ('#' with no space is part of the value) refused ----
printf 'CIPHER_TOKEN_B850_CLAUDE=%s#note\n' "$FAKE_TOKEN" > "$FIXTURE/pmoves/.env.local"
out="$(run_bind b850-claude)"
envv="$(printf '%s\n' "$out" | sed -n 's/^ENV=//p')"
[ -z "$envv" ] && ok "malformed cipher_ value refused" || bad "bound a malformed value"
printf '%s\n' "$out" | grep -q 'not a well-formed' && ok "malformed refusal is loud" || bad "malformed refusal reason missing"

echo
printf 'pm-cipher-token-bind: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
