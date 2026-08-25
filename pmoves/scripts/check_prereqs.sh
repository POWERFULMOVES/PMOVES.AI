#!/usr/bin/env bash
# check_prereqs.sh — verify system binaries required for PMOVES.
#
# Two tiers:
#   bringup (default) — non-Python prerequisites bringup can't pip-install: jq,
#                       make, curl, git, python3. Missing => exit 1 (CI gate /
#                       Make target failure). Unchanged from the original.
#   agent             — the CLI contract an agent session assumes: the agent
#                       binaries themselves plus every tool named as a Known
#                       Road in .claude/BOOTSTRAP.md. Advisory by default
#                       (exit 0), because a node may legitimately lack some;
#                       --strict makes gaps fatal.
#
# Also reports two conditions that masquerade as "package missing":
#   * stale session PATH (Windows) — the binary is installed AND on the
#     persisted PATH, but this shell predates the install and cannot see it.
#   * an active VIRTUAL_ENV — changes which `python` you get.
#
# Exit codes:
#   0  all checked prereqs present (agent-tier gaps advisory unless --strict)
#   1  one or more required prereqs missing
#   2  bad usage
#
# Usage:
#   bash pmoves/scripts/check_prereqs.sh                  # bringup tier (default)
#   bash pmoves/scripts/check_prereqs.sh --agent          # agent CLI contract only
#   bash pmoves/scripts/check_prereqs.sh --all            # both tiers
#   bash pmoves/scripts/check_prereqs.sh --quiet          # only show failures
#   bash pmoves/scripts/check_prereqs.sh --all --strict   # agent gaps are fatal

set -uo pipefail

QUIET=0
STRICT=0
TIER="bringup"

for arg in "$@"; do
  case "$arg" in
    --quiet)  QUIET=1 ;;
    --strict) STRICT=1 ;;
    --agent)  TIER="agent" ;;
    --all)    TIER="all" ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "check_prereqs.sh: unknown argument '$arg' (try --help)" >&2
      exit 2 ;;
  esac
done

# Binary name → one-line install hint per platform (apt | brew | pacman | choco).
declare -A HINTS=(
  [jq]="apt: sudo apt install jq | brew: brew install jq | pacman: sudo pacman -S jq | choco: choco install jq"
  [make]="apt: sudo apt install build-essential | brew: xcode-select --install | pacman: sudo pacman -S base-devel | choco: choco install make"
  [curl]="apt: sudo apt install curl | brew: brew install curl | pacman: sudo pacman -S curl | choco: choco install curl"
  [git]="apt: sudo apt install git | brew: brew install git | pacman: sudo pacman -S git | choco: choco install git"
  [python3]="apt: sudo apt install python3 python3-venv | brew: brew install python | pacman: sudo pacman -S python | choco: choco install python"
  [docker]="https://docs.docker.com/get-docker/ — Known Road: make -C pmoves up-<service>"
  [uv]="curl -LsSf https://astral.sh/uv/install.sh | sh    | winget: winget install astral-sh.uv"
  [uvx]="ships with uv — see the uv hint above"
  [gh]="apt: sudo apt install gh | brew: brew install gh | winget: winget install GitHub.cli"
  [node]="https://nodejs.org or nvm | winget: winget install OpenJS.NodeJS"
  [npm]="ships with node — see the node hint above"
  [tailscale]="https://tailscale.com/download — Known Road: make -C pmoves fleet-status"
  [nats]="winget install NATSAuthors.CLI | brew install nats-io/nats-tools/nats | go install github.com/nats-io/natscli/nats@latest"
  [nsc]="winget install NATSAuthors.nsc | brew install nsc | go install github.com/nats-io/nsc/v2@latest"
  [claude]="https://claude.com/claude-code"
  [crush]="https://github.com/charmbracelet/crush"
  [pterm]="ships with Pinokio — add <pinokio-root>/bin/npm to PATH"
  [rg]="apt: sudo apt install ripgrep | brew: brew install ripgrep | winget: winget install BurntSushi.ripgrep.MSVC"
  [ffmpeg]="apt: sudo apt install ffmpeg | brew: brew install ffmpeg | winget: winget install Gyan.FFmpeg"
)

REQUIRED=(jq make curl git python3)

# The CLI contract an agent session assumes. Grounded in .claude/BOOTSTRAP.md
# Known Roads (make / docker / tailscale / gh / uv), its MCP entrypoint table
# (uvx), the NATS publishers in pmoves/scripts/*.sh (nats), the minted NATS
# trust hierarchy (nsc), and the Pinokio skills (pterm).
AGENT=(claude crush uv uvx gh docker node npm tailscale nats nsc pterm rg ffmpeg)

# check_tier <label> <name-of-array>; returns the number of missing binaries.
check_tier() {
  local label="$1"
  local -n _bins="$2"
  local miss=0
  local bin version

  echo "🔍 ${label}"
  for bin in "${_bins[@]}"; do
    if command -v "$bin" >/dev/null 2>&1; then
      if [[ "$QUIET" -eq 0 ]]; then
        version=$("$bin" --version 2>&1 | head -1 || echo "<version-unknown>")
        printf "  ✅ %-10s %s\n" "$bin" "$version"
      fi
    else
      miss=$((miss+1))
      printf "  ❌ %-10s MISSING — %s\n" "$bin" "${HINTS[$bin]:-<no install hint>}"
    fi
  done
  echo
  return "$miss"
}

# ── Stale-session PATH detection (Windows) ───────────────────────────────────
# A binary can be installed AND on the persisted PATH yet invisible to this
# shell, because Windows never refreshes a running process's environment. That
# reads as "package missing" and sends you chasing a reinstall that won't help.
path_staleness_report() {
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ;; *) return 0 ;; esac
  command -v powershell.exe >/dev/null 2>&1 || return 0
  command -v cygpath >/dev/null 2>&1 || return 0

  local ps_cmd persisted live stale=() d p
  ps_cmd='$m=[Environment]::GetEnvironmentVariable("Path","Machine");'
  ps_cmd+='$u=[Environment]::GetEnvironmentVariable("Path","User");'
  ps_cmd+='(($m+";"+$u) -split ";") | Where-Object { $_.Trim() -ne "" }'

  persisted=$(powershell.exe -NoProfile -Command "$ps_cmd" 2>/dev/null | tr -d '\r')
  [[ -z "$persisted" ]] && return 0

  # Lowercased, trailing-slash-stripped view of the live PATH for comparison.
  live=$(printf '%s' "$PATH" | tr ':' '\n' | sed 's:/\+$::' | tr '[:upper:]' '[:lower:]')

  while IFS= read -r d; do
    [[ -z "$d" ]] && continue
    p=$(cygpath -u "$d" 2>/dev/null) || continue
    p=$(printf '%s' "$p" | sed 's:/\+$::' | tr '[:upper:]' '[:lower:]')
    [[ -z "$p" ]] && continue
    grep -qxF "$p" <<<"$live" || stale+=("$d")
  done <<<"$persisted"

  if [[ ${#stale[@]} -gt 0 ]]; then
    echo "⚠️  Stale session PATH — ${#stale[@]} persisted entr(y|ies) missing from this shell:"
    printf '     %s\n' "${stale[@]}"
    echo "     Anything installed there reads as MISSING above even though it is present."
    echo "     Fix: open a new terminal, or in PowerShell run:"
    echo '       $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")'
    echo
  fi
}

virtualenv_report() {
  [[ -z "${VIRTUAL_ENV:-}" ]] && return 0
  echo "ℹ️  VIRTUAL_ENV active: ${VIRTUAL_ENV}"
  echo "     python resolves to: $(command -v python 2>/dev/null || echo '<none>')"
  echo "     Run 'deactivate' if that is not the interpreter you meant to use."
  echo
}

# ── Run ──────────────────────────────────────────────────────────────────────
req_missing=0
agent_missing=0

if [[ "$TIER" == "bringup" || "$TIER" == "all" ]]; then
  check_tier "Bringup prereqs (required)" REQUIRED || req_missing=$?
fi

if [[ "$TIER" == "agent" || "$TIER" == "all" ]]; then
  check_tier "Agent CLI contract (advisory)" AGENT || agent_missing=$?
fi

path_staleness_report
virtualenv_report

rc=0

if [[ "$req_missing" -gt 0 ]]; then
  echo "❌ $req_missing required prereq(s) missing. Install with the per-platform hint above and re-run."
  echo "   Then: make -C pmoves venv-bringup"
  rc=1
fi

if [[ "$agent_missing" -gt 0 ]]; then
  if [[ "$STRICT" -eq 1 ]]; then
    echo "❌ $agent_missing agent-CLI gap(s) — failing because --strict was given."
    rc=1
  else
    echo "⚠️  $agent_missing agent-CLI gap(s) — advisory, not blocking."
    echo "   Skills and Known Roads that shell out to them degrade or skip silently."
  fi
fi

if [[ "$req_missing" -eq 0 && "$agent_missing" -eq 0 ]]; then
  echo "✅ All checked prereqs present."
fi

exit "$rc"
