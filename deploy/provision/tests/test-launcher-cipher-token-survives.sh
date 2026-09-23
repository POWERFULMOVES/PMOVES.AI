#!/usr/bin/env bash
# test-launcher-cipher-token-survives.sh
# ---------------------------------------------------------------------------
# For each non-claude launcher (codex, crush, hermes, kilo, kimi), prove the
# per-agent cipher token bound by pm-cipher-token-bind.sh is the token the
# harness is finally exec'd with -- i.e. nothing sourced AFTER the bind
# (pm-cipher-identity.sh, crush-env.sh's second pass, tailscale-node-ips.sh)
# puts the node bootstrap bearer back.
#
# Method: a throwaway fixture repo holding the REAL launchers and the REAL
# post-bind fragments, with env.shared / env.tier-agent carrying a bootstrap
# CIPHER_API_TOKEN, .env.local carrying CIPHER_TOKEN_<AGENT>, and stub
# binaries on PATH that record the CIPHER_API_TOKEN they were exec'd with.
# Only pm-node-identity.sh is stubbed (it runs BEFORE the bind and needs a
# resolver + vocabulary; the stub just declares the agentId).
#
# Negative control: a launcher copy that re-exports the bootstrap token after
# the bind MUST be reported as clobbered, or the harness proves nothing.
#
# Run: bash deploy/provision/tests/test-launcher-cipher-token-survives.sh
# ---------------------------------------------------------------------------
set -uo pipefail

SELF_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(CDPATH= cd -P -- "$SELF_DIR/../../.." && pwd)"

pass=0; fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

AGENT="test-agent"
AGENT_TOKEN="cipher_0123456789abcdef0123456789abcdef"
BOOTSTRAP="bootstrap-node-bearer-not-per-agent"

F="$(mktemp -d)"
trap 'find "$F" -mindepth 1 -delete 2>/dev/null; rmdir "$F" 2>/dev/null' EXIT

mkdir -p "$F/pmoves/scripts" "$F/pmoves/configs/claws" "$F/.kimi" "$F/bin" "$F/home"
for s in codex-pmoves.sh crush-pmoves hermes-pmoves kilo-pmoves.sh kimi-pmoves.sh \
         pm-cipher-token-bind.sh pm-cipher-identity.sh crush-env.sh \
         tailscale-node-ips.sh pm-python.sh; do
  if [ -f "$REPO/pmoves/scripts/$s" ]; then
    cp "$REPO/pmoves/scripts/$s" "$F/pmoves/scripts/$s"
  else
    bad "missing source script: pmoves/scripts/$s"
  fi
done
chmod +x "$F/pmoves/scripts/"*

cat > "$F/pmoves/scripts/pm-node-identity.sh" <<'EOF'
# test stub: declares the agentId; the real resolver runs BEFORE the bind.
pm_node_identity() {
  PM_IDENT_OK=1
  PM_IDENT_CIPHER_ID="${TEST_CIPHER_AGENT:-}"
  PM_IDENT_LINE="[stub] node identity"
  PM_IDENT_PY=()
  PMOVES_NODE_IDENTITY="$PM_IDENT_CIPHER_ID"
  export PMOVES_NODE_IDENTITY
  return 0
}
EOF

: > "$F/pmoves/Makefile"
printf 'CIPHER_API_TOKEN=%s\n' "$BOOTSTRAP" > "$F/pmoves/env.shared"
printf 'CIPHER_API_TOKEN=%s\n' "$BOOTSTRAP" > "$F/pmoves/env.tier-agent"
printf 'CIPHER_TOKEN_TEST_AGENT=%s\n' "$AGENT_TOKEN" > "$F/pmoves/.env.local"
printf '{}\n' > "$F/pmoves/configs/claws/opencode-5090.json"
printf '# stub\n' > "$F/.kimi/config.toml"
printf '{"mcpServers":{}}\n' > "$F/.kimi/mcp.json"

# Stubs: each harness binary records the token it was exec'd with.
for b in codex crush hermes opencode kimi; do
  cat > "$F/bin/$b" <<'EOF'
#!/usr/bin/env bash
printf '%s' "${CIPHER_API_TOKEN:-<unset>}" > "$PROBE_OUT"
EOF
done
printf '#!/usr/bin/env bash\nexit 0\n' > "$F/bin/make"
printf '#!/usr/bin/env bash\nexit 1\n' > "$F/bin/tailscale"
chmod +x "$F/bin/"*
git -C "$F" init -q 2>/dev/null

# run_launcher <label> <script> <inherited CIPHER_API_TOKEN or ''> [args...]
run_launcher() {
  local label="$1" script="$2" inherited="$3"; shift 3
  local probe="$F/probe.$label"
  [ -e "$probe" ] && rm "$probe"
  (
    cd "$F" || exit 99
    export PATH="$F/bin:$PATH" HOME="$F/home" PROBE_OUT="$probe" TEST_CIPHER_AGENT="$AGENT"
    unset CIPHER_API_TOKEN PMOVES_ENV_SHARED
    [ -n "$inherited" ] && export CIPHER_API_TOKEN="$inherited"
    bash "$F/pmoves/scripts/$script" "$@"
  ) >"$F/out.$label" 2>&1
  if [ ! -f "$probe" ]; then
    printf '<never-exec>'
  else
    cat "$probe"
  fi
}

check() { # <label> <got>
  case "$2" in
    "$AGENT_TOKEN") ok "$1: exec'd with the bound per-agent token" ;;
    "$BOOTSTRAP")   bad "$1: bootstrap bearer clobbered the bound token" ;;
    "<never-exec>") bad "$1: launcher never reached exec (see output below)"; sed 's/^/        /' "$F/out.${1// /_}" | tail -8 ;;
    *)              bad "$1: unexpected token value (not printed)" ;;
  esac
}

echo "== launcher cipher token survives to exec =="
for pair in "codex:codex-pmoves.sh" "crush:crush-pmoves" "hermes:hermes-pmoves" \
            "kilo:kilo-pmoves.sh" "kimi:kimi-pmoves.sh"; do
  name="${pair%%:*}"; script="${pair#*:}"
  # A: the session env already carries the bootstrap bearer (the real case
  #    when launched from a shell that loaded env.shared).
  label="${name}_inherited"
  check "$label" "$(run_launcher "$label" "$script" "$BOOTSTRAP")"
  # B: clean env; only the repo's env files carry the bootstrap bearer.
  label="${name}_clean"
  check "$label" "$(run_launcher "$label" "$script" "")"
done

# Negative control: inject a bootstrap re-export AFTER the bind in a codex copy.
sed "s|^exec codex|export CIPHER_API_TOKEN=\"$BOOTSTRAP\"\nexec codex|" \
  "$F/pmoves/scripts/codex-pmoves.sh" > "$F/pmoves/scripts/codex-clobber.sh"
got="$(run_launcher control codex-clobber.sh "")"
if [ "$got" = "$BOOTSTRAP" ]; then
  ok "negative control: an injected post-bind clobber IS detected"
else
  bad "negative control: harness did not see an injected clobber"
fi

echo
printf 'launcher-cipher-token-survives: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
