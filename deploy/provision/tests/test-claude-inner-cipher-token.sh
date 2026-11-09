#!/usr/bin/env bash
# test-claude-inner-cipher-token.sh
# ---------------------------------------------------------------------------
# The claude INNER launcher (deploy/provision/claude-pmoves.sh) loads
# env.shared -- which carries the node bootstrap CIPHER_API_TOKEN -- and then
# re-binds from pmoves/.env.local. This proves the token `claude` is finally
# exec'd with, in a fixture repo running the REAL launcher and the REAL bind
# fragment against a stub `claude` that records its env:
#
#   A. explicit cipher_ token exported, NO .env.local key  -> explicit token
#      (before the #3143 item-3 fix this reached claude as the bootstrap)
#   B. clean env, .env.local key                           -> per-agent token
#   C. bootstrap inherited from the shell, .env.local key  -> per-agent token
#   D. explicit cipher_ token AND a .env.local key         -> explicit token
#      (the fragment's documented rule: an explicit env token wins)
#
# Run: bash deploy/provision/tests/test-claude-inner-cipher-token.sh
# ---------------------------------------------------------------------------
set -uo pipefail

SELF_DIR="$(CDPATH='' cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(CDPATH='' cd -P -- "$SELF_DIR/../../.." && pwd)"

pass=0; fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

AGENT="test-agent"
AGENT_TOKEN="cipher_0123456789abcdef0123456789abcdef"
EXPLICIT="cipher_ffffffffffffffffffffffffffffffff"
BOOTSTRAP="bootstrap-node-bearer-not-per-agent"

F="$(mktemp -d)"
trap 'find "$F" -mindepth 1 -delete 2>/dev/null; rmdir "$F" 2>/dev/null' EXIT

mkdir -p "$F/deploy/provision" "$F/pmoves/scripts" "$F/bin" "$F/home" "$F/.claude"
cp "$REPO/deploy/provision/claude-pmoves.sh" "$F/deploy/provision/claude-pmoves.sh"
cp "$REPO/pmoves/scripts/pm-cipher-token-bind.sh" "$F/pmoves/scripts/pm-cipher-token-bind.sh"
: > "$F/pmoves/Makefile"
printf 'CIPHER_API_TOKEN=%s\n' "$BOOTSTRAP" > "$F/pmoves/env.shared"
printf '{"mcpServers":{}}\n' > "$F/.claude/mcp.json"
cat > "$F/bin/claude" <<'EOF'
#!/usr/bin/env bash
printf '%s' "${CIPHER_API_TOKEN:-<unset>}" > "$PROBE_OUT"
EOF
chmod +x "$F/bin/claude"

# run_inner <label> <inherited token or ''> <write .env.local key: yes|no>
run_inner() {
  local label="$1" inherited="$2" withkey="$3" probe="$F/probe.$1"
  if [ "$withkey" = yes ]; then
    printf 'CIPHER_TOKEN_TEST_AGENT=%s\n' "$AGENT_TOKEN" > "$F/pmoves/.env.local"
  else
    printf 'UNRELATED=1\n' > "$F/pmoves/.env.local"
  fi
  (
    cd "$F" || exit 99
    export PATH="$F/bin:$PATH" HOME="$F/home" PROBE_OUT="$probe" PM_IDENT_CIPHER_ID="$AGENT"
    unset CIPHER_API_TOKEN PMOVES_ENV_SHARED PMOVES_LAUNCHER_ROOT
    [ -n "$inherited" ] && export CIPHER_API_TOKEN="$inherited"
    timeout 60 bash "$F/deploy/provision/claude-pmoves.sh" --version
  ) >"$F/out.$label" 2>&1
  if [ -f "$probe" ]; then cat "$probe"; else printf '<never-exec>'; fi
}

expect() { # <label> <got> <want> <want-name>
  if [ "$2" = "$3" ]; then
    ok "$1: exec'd with the $4 token"
  else
    case "$2" in
      "$BOOTSTRAP")   bad "$1: exec'd with the BOOTSTRAP bearer (wanted $4)" ;;
      "<never-exec>") bad "$1: launcher never reached exec"; tail -5 "$F/out.$1" | sed 's/^/        /' ;;
      *)              bad "$1: exec'd with an unexpected token (wanted $4; value not printed)" ;;
    esac
  fi
}

echo "== claude inner launcher: cipher token at exec =="
expect A_explicit_no_key       "$(run_inner A_explicit_no_key "$EXPLICIT" no)"   "$EXPLICIT"    "explicit"
expect B_clean_with_key        "$(run_inner B_clean_with_key "" yes)"           "$AGENT_TOKEN" "per-agent"
expect C_bootstrap_with_key    "$(run_inner C_bootstrap_with_key "$BOOTSTRAP" yes)" "$AGENT_TOKEN" "per-agent"
expect D_explicit_with_key     "$(run_inner D_explicit_with_key "$EXPLICIT" yes)" "$EXPLICIT"    "explicit"

# The captured variable must not leak into the session env.
cat > "$F/bin/claude" <<'EOF'
#!/usr/bin/env bash
if [ -n "${PM_CIPHER_PRE_ENV_TOKEN+x}" ]; then printf 'LEAKED' > "$PROBE_OUT"; else printf 'clean' > "$PROBE_OUT"; fi
EOF
chmod +x "$F/bin/claude"
got="$(run_inner E_no_leak "$EXPLICIT" no)"
[ "$got" = "clean" ] && ok "E: PM_CIPHER_PRE_ENV_TOKEN does not reach the session env" || bad "E: capture variable leaked into the session env ($got)"

echo
printf 'claude-inner-cipher-token: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
