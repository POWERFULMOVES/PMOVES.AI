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
# Every binary lands in one of three states, not two:
#   present   — resolves on this shell's PATH.
#   SHADOWED  — installed and on the *persisted* PATH, but invisible to this
#               shell, because Windows never refreshes a running process's
#               environment. Reinstalling cannot fix it; a new terminal can.
#   MISSING   — not found anywhere this script can see. Install it.
#
# Separating SHADOWED from MISSING is the point of the PATH scan: without it a
# stale session reports a fully-provisioned machine as N missing packages and
# sends you chasing reinstalls that cannot help.
#
# Also reports an active VIRTUAL_ENV, which changes which `python` you get.
#
# Exit codes:
#   0  all checked prereqs usable (agent-tier gaps advisory unless --strict)
#   1  one or more required prereqs missing or shadowed
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
      # Print the header block: line 2 through the last leading comment line.
      # Robust against the header changing length.
      sed -n '2,${/^#/!q;p;}' "$0" | sed 's/^# \{0,1\}//'
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

# ── Stale-session PATH scan (Windows) ────────────────────────────────────────
# Persisted PATH directories this shell cannot see, plus an index of what lives
# in them. Populated once, before any tier runs, so check_tier can tell
# SHADOWED apart from MISSING.
STALE_DIRS=()              # Windows form, for display
STALE_DIRS_U=()            # same entries, POSIX form, parallel index
declare -A STALE_BINS=()   # lowercased filename -> display path, PATH order
STALE_INDEXED=0

path_staleness_scan() {
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ;; *) return 0 ;; esac
  command -v powershell.exe >/dev/null 2>&1 || return 0
  command -v cygpath >/dev/null 2>&1 || return 0

  local ps_cmd persisted live d p
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
    p="${p%/}"
    [[ -z "$p" ]] && continue
    grep -qxF "${p,,}" <<<"$live" || { STALE_DIRS+=("$d"); STALE_DIRS_U+=("$p"); }
  done <<<"$persisted"
}

# stale_index_build — map every filename under the stale directories to where it
# lives. Built at most once, and only if something actually failed to resolve,
# so a healthy session pays nothing for it.
#
# Reading directory entries rather than stat-ing candidate names is a
# correctness requirement, not just a speed one: MSYS's stat() transparently
# appends .exe, so `-f <dir>/claude` succeeds for claude.exe and would report a
# filename that does not exist on disk. Globbing gives the real spelling.
#
# Deliberately fork-free — no ls, no tr. This runs on the venv-bringup path,
# where every subprocess costs ~250ms on Windows.
stale_index_build() {
  [[ "$STALE_INDEXED" -eq 1 ]] && return 0
  STALE_INDEXED=1

  local i u f key had_nullglob=0
  shopt -q nullglob && had_nullglob=1
  shopt -s nullglob

  # First writer wins, so lookups resolve in persisted-PATH order.
  for ((i = 0; i < ${#STALE_DIRS_U[@]}; i++)); do
    u="${STALE_DIRS_U[i]}"
    [[ -d "$u" ]] || continue
    for f in "$u"/*; do
      [[ -f "$f" ]] || continue
      f="${f##*/}"
      key="${f,,}"
      [[ -n "${STALE_BINS[$key]:-}" ]] || STALE_BINS["$key"]="${STALE_DIRS[i]%\\}\\${f}"
    done
  done

  [[ "$had_nullglob" -eq 1 ]] || shopt -u nullglob
}

# find_in_stale <bin> — echo where <bin> lives under a stale PATH directory, or
# return 1. The extension list mirrors what `command -v` would have matched had
# the directory been on the live PATH; bare name first, as MSYS resolves it.
find_in_stale() {
  local bin ext key
  [[ ${#STALE_DIRS_U[@]} -eq 0 ]] && return 1
  stale_index_build
  bin="${1,,}"
  for ext in "" .exe .cmd .bat .com; do
    key="${bin}${ext}"
    if [[ -n "${STALE_BINS[$key]:-}" ]]; then
      printf '%s\n' "${STALE_BINS[$key]}"
      return 0
    fi
  done
  return 1
}

# check_tier <label> <name-of-array>
# Sets TIER_MISSING and TIER_SHADOWED. The two counts stay separate because the
# remedies are opposite: install vs. restart the terminal.
TIER_MISSING=0
TIER_SHADOWED=0

check_tier() {
  local label="$1"
  local -n _bins="$2"
  local bin version found_at

  TIER_MISSING=0
  TIER_SHADOWED=0

  echo "🔍 ${label}"
  for bin in "${_bins[@]}"; do
    if command -v "$bin" >/dev/null 2>&1; then
      if [[ "$QUIET" -eq 0 ]]; then
        # Not `... || echo <unknown>`: under pipefail a tool that prints its
        # banner but exits non-zero on an unrecognised --version (ffmpeg wants
        # -version) would emit both the banner and the fallback.
        version=$("$bin" --version 2>&1 | head -1)
        [[ -n "$version" ]] || version="<version-unknown>"
        printf "  ✅ %-10s %s\n" "$bin" "$version"
      fi
    elif found_at=$(find_in_stale "$bin"); then
      TIER_SHADOWED=$((TIER_SHADOWED+1))
      printf "  ⚠️  %-10s SHADOWED — installed at %s, not on this shell's PATH\n" "$bin" "$found_at"
    else
      TIER_MISSING=$((TIER_MISSING+1))
      printf "  ❌ %-10s MISSING — %s\n" "$bin" "${HINTS[$bin]:-<no install hint>}"
    fi
  done
  echo
}

path_staleness_report() {
  [[ ${#STALE_DIRS[@]} -eq 0 ]] && return 0
  echo "⚠️  Stale session PATH — ${#STALE_DIRS[@]} persisted entr(y|ies) missing from this shell:"
  printf '     %s\n' "${STALE_DIRS[@]}"
  echo "     Anything flagged SHADOWED above resolves from one of these."
  echo "     Fix: open a new terminal, or in PowerShell run:"
  echo '       $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")'
  echo
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
req_shadowed=0
agent_missing=0
agent_shadowed=0

path_staleness_scan

if [[ "$TIER" == "bringup" || "$TIER" == "all" ]]; then
  check_tier "Bringup prereqs (required)" REQUIRED
  req_missing=$TIER_MISSING
  req_shadowed=$TIER_SHADOWED
fi

if [[ "$TIER" == "agent" || "$TIER" == "all" ]]; then
  check_tier "Agent CLI contract (advisory)" AGENT
  agent_missing=$TIER_MISSING
  agent_shadowed=$TIER_SHADOWED
fi

path_staleness_report
virtualenv_report

rc=0

if [[ "$req_missing" -gt 0 ]]; then
  echo "❌ $req_missing required prereq(s) missing. Install with the per-platform hint above and re-run."
  echo "   Then: make -C pmoves venv-bringup"
  rc=1
fi

# Shadowed is fatal wherever missing is fatal — this shell genuinely cannot
# invoke the binary. Only the remedy differs, so only the message does.
if [[ "$req_shadowed" -gt 0 ]]; then
  echo "❌ $req_shadowed required prereq(s) installed but invisible to this shell."
  echo "   Open a new terminal and re-run — do not reinstall."
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

if [[ "$agent_shadowed" -gt 0 ]]; then
  if [[ "$STRICT" -eq 1 ]]; then
    echo "❌ $agent_shadowed agent CLI(s) installed but invisible to this shell — failing because --strict was given."
    echo "   Open a new terminal and re-run — do not reinstall."
    rc=1
  else
    echo "⚠️  $agent_shadowed agent CLI(s) installed but invisible to this shell."
    echo "   Open a new terminal — do not reinstall."
  fi
fi

if [[ $((req_missing + req_shadowed + agent_missing + agent_shadowed)) -eq 0 ]]; then
  echo "✅ All checked prereqs present."
fi

exit "$rc"
