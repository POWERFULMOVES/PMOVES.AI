#!/usr/bin/env bash
# pm-cipher-token-bind.sh — bind a minted per-agent cipher token into the
# session environment, so the MCP roster's `Bearer ${CIPHER_API_TOKEN}`
# materializes the TOKEN FOR THIS AGENT, not the node bootstrap token.
# ===========================================================================
# WHY THIS EXISTS
# ---------------
# auth.ts (@ Pmoves-cipher) forks on the bearer shape: a `cipher_`-prefixed
# token resolves per-agent via pmoves_core.cipher_agent_tokens; anything else
# is compared against the server's single CIPHER_API_TOKEN env and files every
# write under 'bootstrap'. The launchers resolve the session's real cipher
# agentId (b850-claude) and TELL the model to declare it — while the roster
# still carried the bootstrap bearer, so every declared-id call 403'd and every
# undeclared call polluted the shared 'bootstrap' corpus. The mint path
# (pmoves/scripts/mint_cipher_token.py, card-gated) was built for exactly this
# handoff; the last mile — getting the minted token INTO the session env —
# was never wired ("a token cannot be minted from a launcher without putting
# a secret through a shell"). This fragment is that last mile, reading tokens
# that were minted OUT OF BAND through the sanctioned path.
#
# THE CONTRACT
# ------------
# pm_cipher_token_bind <repo_root> <agent_id>
#
#   returns 0  a per-agent token is now exported as CIPHER_API_TOKEN
#              (or one already was — explicit operator env wins)
#   returns 1  no bind; PM_CARRY_BIND_LINE says WHY, and the caller must
#              still print it
#
# On return, ALWAYS set:
#   PM_CARRY_BIND_LINE   one line for stderr, already prefixed by the caller
#   PM_CARRY_BIND_OK     1 when the session now carries a cipher_ token
#
# TOKEN STORE
# -----------
# pmoves/.env.local (gitignored, machine-specific — the documented per-node
# override file; with-env.sh already loads it LAST):
#
#     CIPHER_TOKEN_B850_CLAUDE=cipher_<uuidhex>
#     CIPHER_TOKEN_KNUCKLES_KIMI=cipher_<uuidhex>
#
# Key = CIPHER_TOKEN_ + agent_id uppercased with '-' -> '_'. One key per
# declared cipher identity on the node. The value is a minted bearer from
# mint_cipher_token.py; the row in cipher_agent_tokens IS the credential
# (token_uuid is stored verbatim), so a row minted out-of-band can be bound
# by writing its bearer here — no re-mint, no duplicate rows.
#
# WHY A TARGETED READ AND NOT `source .env.local`
# ------------------------------------------------
# The launcher must not execute or fully export an operator file that also
# feeds compose services (pmoves-ui, cloudflared, ... list .env.local with
# required:false). We read exactly ONE key, never eval, never expand: the
# value is expected to be a bare `cipher_<hex>` token.
#
# NEVER prints, logs, or reads past the prefix of the bearer. An operator
# override (CIPHER_API_TOKEN already cipher_-prefixed in the env) is
# respected and reported — the carry measurement downstream still verifies
# that whatever is carried resolves to the declared agent.
#
# SCOPE OF THAT GUARANTEE: the rule holds when this function runs. A caller
# that loads env.shared (the node bootstrap bearer) BEFORE calling it must
# preserve an explicit token itself. The one launcher that does so,
# deploy/provision/claude-pmoves.sh (the claude inner launcher), captures a
# cipher_ token before loading env.shared and restores it just before its
# re-bind, so an explicit token reaches `claude` with or without a
# CIPHER_TOKEN_<AGENT> key in pmoves/.env.local
# (deploy/provision/tests/test-claude-inner-cipher-token.sh). The five
# non-claude launchers load nothing after the bind that can overwrite it
# (deploy/provision/tests/test-launcher-cipher-token-survives.sh).
#
# ALWAYS LOUD ON SKIP, same rule as pm-cipher-identity.sh: a session that
# silently kept bootstrap is the exact defect this fragment exists to end.

pm_cipher_token_bind() {
  local root="${1:-}" agent="${2:-}"

  PM_CARRY_BIND_LINE=""
  PM_CARRY_BIND_OK=0

  if [ -z "$agent" ]; then
    PM_CARRY_BIND_LINE="cipher token=unbound — no declared cipher agentId for this harness on this node (nothing to bind; add an agentId to node-vocabulary.yaml and mint: make -C pmoves cipher-mint-token)"
    return 1
  fi

  # Explicit operator/env token wins. Reported, not silently kept — the carry
  # measurement verifies it actually resolves to the declared agent.
  case "${CIPHER_API_TOKEN:-}" in
    cipher_*)
      PM_CARRY_BIND_OK=1
      PM_CARRY_BIND_LINE="cipher token=already per-agent (explicit CIPHER_API_TOKEN in env respected)"
      return 0
      ;;
  esac

  local key
  key="CIPHER_TOKEN_$(printf '%s' "$agent" | tr '[:lower:]-' '[:upper:]_')"

  local envf="${root}/pmoves/.env.local"
  if [ ! -f "$envf" ]; then
    PM_CARRY_BIND_LINE="cipher token=unbound — ${envf} absent; create it and add ${key}=cipher_... (mint: make -C pmoves cipher-mint-token AGENT=${agent})"
    return 1
  fi

  # Targeted, non-evaluating read: first line whose name is EXACTLY $key.
  # Fixed-string field compare, not a regex: an agentId carrying `.`, `+` or
  # `*` would otherwise be interpreted as ERE metacharacters. Then: a trailing
  # ` # comment` is dropped (whitespace-then-#, the env_file rule; a `#` with
  # no whitespace before it stays part of the value, as compose reads it),
  # whitespace trimmed, one layer of matching quotes stripped. Never a shell
  # expansion of the value.
  local line
  line="$(awk -F= -v k="$key" '$1 == k { print; exit }' "$envf" 2>/dev/null)" || line=""
  local tok="${line#*=}"
  tok="${tok%%[[:space:]]#*}"
  tok="${tok#"${tok%%[![:space:]]*}"}"; tok="${tok%"${tok##*[![:space:]]}"}"
  tok="${tok#\"}"; tok="${tok%\"}"
  tok="${tok#\'}"; tok="${tok%\'}"
  tok="${tok#"${tok%%[![:space:]]*}"}"; tok="${tok%"${tok##*[![:space:]]}"}"

  if [ -z "$tok" ]; then
    PM_CARRY_BIND_LINE="cipher token=unbound — ${key} not in ${envf} (mint: make -C pmoves cipher-mint-token AGENT=${agent})"
    return 1
  fi
  # Shape check: minted bearers are `cipher_<uuid4 hex>` (mint_cipher_token.py).
  # Anything else after the prefix -- a leftover `#note`, a space, a `$` -- is a
  # malformed value, and exporting it would present a bearer that cannot match.
  case "$tok" in
    cipher_*[!0-9A-Za-z-]*|cipher_)
      PM_CARRY_BIND_LINE="cipher token=unbound — ${key} in ${envf} is not a well-formed cipher_<hex> token (refusing to bind it)"
      return 1
      ;;
    cipher_*) : ;;
    *)
      PM_CARRY_BIND_LINE="cipher token=unbound — ${key} in ${envf} is not a cipher_-prefixed token (refusing to bind it)"
      return 1
      ;;
  esac

  export CIPHER_API_TOKEN="$tok"
  PM_CARRY_BIND_OK=1
  PM_CARRY_BIND_LINE="cipher token=bound for ${agent} (${key} from pmoves/.env.local)"
  return 0
}
