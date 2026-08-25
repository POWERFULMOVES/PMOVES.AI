#!/usr/bin/env bash
# check_prereqs.sh — verify system binaries required for PMOVES.
#
# Three tiers:
#   bringup (default) — non-Python prerequisites bringup can't pip-install: jq,
#                       make, curl, git, python3. Missing => exit 1 (CI gate /
#                       Make target failure). Unchanged from the original.
#   agent             — the CLI contract an agent session assumes: the agent
#                       binaries themselves plus every tool named as a Known
#                       Road in .claude/BOOTSTRAP.md. Advisory by default
#                       (exit 0), because a node may legitimately lack some;
#                       --strict makes gaps fatal.
#   env               — the bringup interpreter and whether the modules the
#                       tools actually import are importable BY IT. A binary on
#                       PATH is half the contract; the other half is the
#                       interpreter the Make targets shell out through.
#
# A gap prints what it UNLOCKS, not merely that it is absent. A missing CLI
# rarely breaks loudly -- it removes a capability elsewhere, in a skill or Make
# target that then degrades or skips silently. `nats` missing does not error;
# it takes the GEOMETRY BUS offline. `glances` missing does not error; the node
# probe stops writing hardware profiles. Naming the consequence is the
# difference between "install this" and "here is what you cannot currently do".
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
#   bash pmoves/scripts/check_prereqs.sh --env            # bringup interpreter + tool imports
#   bash pmoves/scripts/check_prereqs.sh --all            # all tiers
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
    --env)    TIER="env" ;;
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
  [glances]="make -C pmoves venv-bringup (INCLUDE_BRINGUP=1 installs it) | pipx install glances"
)

# What a binary UNLOCKS, not just that it is absent. A missing CLI does not
# usually break loudly here -- it removes a capability somewhere else, often in
# a skill or Make target that then degrades or skips silently. Naming the
# consequence is the difference between "install this" and "here is what you
# currently cannot do".
#
# Each claim is grounded in a file in this repo, not inferred. Keep it that way:
# an unlocks line that overstates is worse than none, because it will be trusted.
declare -A UNLOCKS=(
  [nats]="GEOMETRY BUS + CHIT event surface (.claude/context/geometry-nats-subjects.md); the nats:* skills and the publishers in pmoves/scripts/*.sh degrade to a silent skip"
  [nsc]="minting/inspecting NATS creds against the trust hierarchy (operator PMOVES + SYS/CORE/EDGE/CLOUD)"
  [glances]="node hardware/network probe — deploy/provision/glances-autodetect.{sh,ps1} and the node-*-probe skills that write pmoves/config/profiles/<node>.yaml"
  [tailscale]="fleet reachability + cross-node delegation; Known Road \`make -C pmoves fleet-status\`"
  [docker]="every \`make -C pmoves up-<service>\` Known Road, and the docker MCP server in .claude/mcp.json"
  [uv]="the uv/uvx-launched MCP servers in .claude/mcp.json, and venv-bringup's installer path"
  [uvx]="stdio MCP entrypoints launched as \`uvx <server>\` (see .claude/mcp.json)"
  [gh]="PR/CI Known Roads; the coding-plan policy routes GitHub work through gh rather than raw API calls"
  [pterm]="the pinokio:* skills (app-list/start/stop/search) and Pinokio clipboard/notify helpers"
  [node]="npx-launched MCP servers in .claude/mcp.json"
  [npm]="same as node — npx-launched MCP servers"
  [ffmpeg]="the media pipeline (YouTube/Whisper ingest, a2ui-renderer video output)"
  [rg]="fast repo search; note plain grep treats AGNOTE4482PHI.t1.md as binary, so rg is not a like-for-like substitute"
  [claude]="Claude Code sessions on this node, including the claude-pmoves launcher"
  [crush]="the PMOVES-Crush lane (GLM/Kimi coding plans)"
  [python3]="every Make target that shells out to pmoves/tools/*.py"
  [jq]="JSON handling in the bringup and smoke-test scripts"
  [make]="the Known Roads themselves — nearly every documented operation is a make target"
  [git]="submodule fleet, worktrees, and the claim/branch workflow"
  [curl]="health probes in the smoke tests and bringup scripts"
)

REQUIRED=(jq make curl git python3)

# The CLI contract an agent session assumes. Grounded in .claude/BOOTSTRAP.md
# Known Roads (make / docker / tailscale / gh / uv), its MCP entrypoint table
# (uvx), the NATS publishers in pmoves/scripts/*.sh (nats), the minted NATS
# trust hierarchy (nsc), and the Pinokio skills (pterm).
AGENT=(claude crush uv uvx gh docker node npm tailscale nats nsc pterm rg ffmpeg glances)

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
      [[ -n "${UNLOCKS[$bin]:-}" ]] && printf "     %-10s dark while shadowed: %s\n" "" "${UNLOCKS[$bin]}"
    else
      TIER_MISSING=$((TIER_MISSING+1))
      printf "  ❌ %-10s MISSING — %s\n" "$bin" "${HINTS[$bin]:-<no install hint>}"
      [[ -n "${UNLOCKS[$bin]:-}" ]] && printf "     %-10s unlocks: %s\n" "" "${UNLOCKS[$bin]}"
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

# ── Interpreter / bringup-environment tier ───────────────────────────────────
# A binary on PATH is only half the contract. The Make targets shell out to
# tools/*.py through PYTHON / PRECHECK_PY / CODEX_PY, and those resolve to an
# interpreter that may not be the provisioned one -- in which case tool
# dependencies are missing and the target degrades rather than failing.
#
# The failure that motivated this: `make sign-trail` could not import yaml, so
# it signed a provenance record with a FALLBACK identity ("this is NOT the
# agent's registered identity") while the provisioned environment sat alongside
# with yaml installed. Nothing on PATH was wrong. Checking binaries would never
# have caught it.
#
# Probed rather than declared: `yaml` is the single most-imported module across
# pmoves/tools/*.py and is NOT listed in tools/requirements.txt, so a
# declaration-only check reports healthy while sign-trail is broken.
BRINGUP_MODULES=(yaml httpx nats jsonschema)

env_tier_report() {
  # Derived from the script's own location, not the cwd: the Make target runs
  # `bash scripts/check_prereqs.sh` from inside pmoves/, while an operator runs
  # `bash pmoves/scripts/check_prereqs.sh` from the repo root. A cwd-relative
  # path is correct for exactly one of those.
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  local win="$root/.venv-pmoves/Scripts/python.exe"
  local nix="$root/.venv-pmoves/bin/python"
  local interp="" layout=""

  echo "🔍 Bringup interpreter (advisory)"

  if [[ -x "$win" ]]; then
    interp="$win"; layout="Windows (Scripts/python.exe)"
  elif [[ -x "$nix" ]]; then
    interp="$nix"; layout="POSIX (bin/python)"
  fi

  if [[ -z "$interp" ]]; then
    printf "  ❌ %-22s not provisioned — looked for both layouts under %s\n" \
      "bringup env" "$root/.venv-pmoves/"
    echo "     Remedy: make -C pmoves venv-bringup"
    echo "     Until then, Make targets fall back to whatever python is on PATH,"
    echo "     and tool imports may be missing without the target saying so."
    echo
    ENV_MISSING=1
    return 0
  fi

  printf "  ✅ %-22s %s\n" "bringup env" "$layout"
  if [[ "$QUIET" -eq 0 ]]; then
    printf "  %-25s %s\n" "" "$("$interp" -c 'import sys;print(sys.version.split()[0])' 2>/dev/null || echo '?')"
  fi

  local m gaps=0
  for m in "${BRINGUP_MODULES[@]}"; do
    # -I (isolated): keeps the cwd OFF sys.path. Without it the probe is
    # cwd-sensitive and lies -- pmoves/ contains a `nats/` directory that
    # shadows the real nats-py package, so a plain `import nats` PASSES from
    # pmoves/ and FAILS from the repo root, for the same interpreter. An
    # instrument that reports fine without having measured anything is the
    # exact failure this tier exists to catch.
    if "$interp" -I -c "import $m" >/dev/null 2>&1; then
      [[ "$QUIET" -eq 0 ]] && printf "  ✅ %-22s importable\n" "$m"
    else
      printf "  ❌ %-22s NOT importable by the bringup interpreter\n" "$m"
      gaps=$((gaps + 1))
    fi
  done

  if [[ "$gaps" -gt 0 ]]; then
    echo "     Remedy: make -C pmoves venv-bringup   (re-runs the install)"
    ENV_MISSING=$((ENV_MISSING + gaps))
  fi
  echo
}

# ── Run ──────────────────────────────────────────────────────────────────────
req_missing=0
req_shadowed=0
agent_missing=0
agent_shadowed=0
ENV_MISSING=0

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

if [[ "$TIER" == "env" || "$TIER" == "agent" || "$TIER" == "all" ]]; then
  env_tier_report
fi

path_staleness_report
virtualenv_report

rc=0

if [[ "$ENV_MISSING" -gt 0 ]]; then
  echo "⚠️  bringup interpreter gap(s) — advisory, not blocking."
  echo "   Make targets that shell out to tools/*.py will use a fallback interpreter;"
  echo "   sign-trail in particular then signs with a FALLBACK identity."
fi

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

if [[ $((req_missing + req_shadowed + agent_missing + agent_shadowed + ENV_MISSING)) -eq 0 ]]; then
  echo "✅ All checked prereqs present."
fi

exit "$rc"
