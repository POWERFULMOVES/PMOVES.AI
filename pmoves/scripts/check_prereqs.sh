#!/usr/bin/env bash
# check_prereqs.sh — verify the tools and interpreter PMOVES work assumes.
#
# Three tiers:
#   bringup (default) — non-Python prerequisites bringup can't install: jq,
#                       make, curl, git, python3. Missing => exit 1. This tier
#                       is unchanged from the original; `venv-bringup` depends
#                       on it and CI-shaped callers must keep their contract.
#   agent  (--agent)  — the CLI contract an agent session assumes. Advisory:
#                       a node may legitimately lack some.
#   env    (--env)    — the bringup interpreter, and whether the modules the
#                       tools actually import are importable BY IT. A binary on
#                       PATH is half the contract; the other half is the
#                       interpreter the Make targets shell out through.
#
# --strict promotes every advisory gap (agent AND env) to a failure.
#
# A gap reports what it UNLOCKS, not merely that it is absent. A missing CLI
# here rarely breaks loudly — it removes a capability elsewhere, in a skill or
# Make target that then degrades or skips silently. `nats` missing does not
# error; it takes the GEOMETRY BUS offline. Naming the consequence is the
# difference between "install this" and "here is what you cannot do".
#
# On Windows the report ends with a stale-PATH banner when the persisted PATH
# holds directories this shell cannot see. That is the single most common cause
# of a tool that is installed reading as MISSING, and reinstalling cannot fix
# it — only a new terminal can.
#
# Exit codes:
#   0  all checked prereqs usable (advisory gaps do not fail unless --strict)
#   1  a required prereq is missing, or --strict and any gap exists
#   2  bad usage
#
# Usage:
#   bash pmoves/scripts/check_prereqs.sh                  # bringup (default)
#   bash pmoves/scripts/check_prereqs.sh --agent          # agent CLI contract
#   bash pmoves/scripts/check_prereqs.sh --env            # interpreter + imports
#   bash pmoves/scripts/check_prereqs.sh --all            # all three
#   bash pmoves/scripts/check_prereqs.sh --all --strict   # gaps are fatal
#   bash pmoves/scripts/check_prereqs.sh --quiet          # only show failures

set -uo pipefail

QUIET=0
STRICT=0
TIER=""

for arg in "$@"; do
  case "$arg" in
    --quiet)  QUIET=1 ;;
    --strict) STRICT=1 ;;
    --agent|--env|--all)
      # Explicit conflict rather than last-wins: `--agent --env` silently
      # dropping a tier and still exiting 0 is a wrong answer, not a shortcut.
      new="${arg#--}"
      if [[ -n "$TIER" && "$TIER" != "$new" ]]; then
        echo "check_prereqs.sh: --$TIER and $arg conflict; use --all" >&2
        exit 2
      fi
      TIER="$new" ;;
    -h|--help)
      sed -n '2,${/^#/!q;p;}' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "check_prereqs.sh: unknown argument '$arg' (try --help)" >&2
      exit 2 ;;
  esac
done
[[ -z "$TIER" ]] && TIER="bringup"

declare -A HINTS=(
  [jq]="apt: sudo apt install jq | brew: brew install jq | winget: winget install jqlang.jq"
  [make]="apt: sudo apt install build-essential | brew: xcode-select --install | winget: winget install GnuWin32.Make"
  [curl]="apt: sudo apt install curl | brew: brew install curl | winget: winget install cURL.cURL"
  [git]="apt: sudo apt install git | brew: brew install git | winget: winget install Git.Git"
  [python3]="apt: sudo apt install python3 python3-venv | brew: brew install python | winget: winget install Python.Python.3.12"
  [docker]="https://docs.docker.com/get-docker/"
  [uv]="curl -LsSf https://astral.sh/uv/install.sh | sh   |   winget install astral-sh.uv"
  [uvx]="ships with uv"
  [gh]="apt: sudo apt install gh | brew: brew install gh | winget: winget install GitHub.cli"
  [node]="https://nodejs.org or nvm | winget: winget install OpenJS.NodeJS"
  [npm]="ships with node"
  [tailscale]="https://tailscale.com/download"
  [nats]="winget install NATSAuthors.CLI | brew install nats-io/nats-tools/nats"
  [nsc]="winget install NATSAuthors.nsc | brew install nsc"
  [claude]="https://claude.com/claude-code"
  [crush]="https://github.com/charmbracelet/crush"
  [pterm]="ships with Pinokio — add <pinokio-root>/bin/npm to PATH"
  [rg]="apt: sudo apt install ripgrep | brew: brew install ripgrep | winget: winget install BurntSushi.ripgrep.MSVC"
  [ffmpeg]="apt: sudo apt install ffmpeg | brew: brew install ffmpeg | winget: winget install Gyan.FFmpeg"
  [glances]="make -C pmoves venv-bringup (INCLUDE_BRINGUP=1 installs it)"
)

# Each claim is grounded in a file in this repo, not inferred. Keep it that way:
# an unlocks line that overstates is worse than none, because it will be trusted.
declare -A UNLOCKS=(
  [nats]="GEOMETRY BUS + CHIT event surface (.claude/context/geometry-nats-subjects.md); the nats:* skills and the publishers in pmoves/scripts/*.sh skip silently without it"
  [nsc]="minting/inspecting NATS creds against the trust hierarchy"
  [glances]="node hardware/network probe — deploy/provision/glances-autodetect.{sh,ps1} and the node-*-probe skills that write pmoves/config/profiles/<node>.yaml"
  [tailscale]="fleet reachability; Known Road 'make -C pmoves fleet-status'"
  [docker]="every 'make -C pmoves up-<service>' Known Road, and the docker MCP server in .claude/mcp.json"
  [uv]="the uv/uvx-launched MCP servers in .claude/mcp.json"
  [uvx]="stdio MCP entrypoints launched as 'uvx <server>'"
  [gh]="PR/CI Known Roads; the coding-plan policy routes GitHub work through gh"
  [pterm]="the pinokio:* skills and Pinokio clipboard/notify helpers"
  [node]="npx-launched MCP servers in .claude/mcp.json"
  [npm]="npx-launched MCP servers"
  [ffmpeg]="the media pipeline (YouTube/Whisper ingest, a2ui-renderer output)"
  [rg]="fast repo search"
  [claude]="Claude Code sessions on this node, including the claude-pmoves launcher"
  [crush]="the PMOVES-Crush lane"
  [python3]="every Make target that shells out to pmoves/tools/*.py"
  [make]="the Known Roads themselves — nearly every documented operation is a make target"
)

REQUIRED=(jq make curl git python3)

# Grounded in .claude/BOOTSTRAP.md Known Roads (make/docker/tailscale/gh/uv),
# its MCP entrypoint table (uvx/node/npm), the NATS publishers in
# pmoves/scripts/*.sh (nats), the minted trust hierarchy (nsc), the Pinokio
# skills (pterm) and the node probes (glances).
AGENT=(claude crush uv uvx gh docker node npm tailscale nats nsc pterm rg ffmpeg glances)

# Probed by counting real imports across pmoves/tools/*.py, not by reading a
# manifest: `yaml` is the most-imported module there and is declared in NO
# requirements file, so a declaration-driven check reports healthy while
# sign-trail is broken.
BRINGUP_MODULES=(yaml httpx nats jsonschema)

TIER_MISSING=0

check_tier() {
  local label="$1"; local -n _bins="$2"
  local bin version
  TIER_MISSING=0
  echo "🔍 ${label}"
  for bin in "${_bins[@]}"; do
    if command -v "$bin" >/dev/null 2>&1; then
      if [[ "$QUIET" -eq 0 ]]; then
        # </dev/null so a tool that reads stdin on an unrecognised flag cannot
        # hang the run; ffmpeg wants -version and exits non-zero on --version.
        version=$("$bin" --version 2>&1 </dev/null | head -1)
        [[ -n "$version" ]] || version="<version-unknown>"
        printf "  ✅ %-10s %s\n" "$bin" "$version"
      fi
    else
      TIER_MISSING=$((TIER_MISSING+1))
      printf "  ❌ %-10s MISSING — %s\n" "$bin" "${HINTS[$bin]:-<no install hint>}"
      [[ -n "${UNLOCKS[$bin]:-}" ]] && printf "     %-10s unlocks: %s\n" "" "${UNLOCKS[$bin]}"
    fi
  done
  echo
}

ENV_MISSING=0
ENV_GAPS=""

env_tier_report() {
  # Root from BASH_SOURCE, not cwd: the Make target runs this from inside
  # pmoves/ while an operator runs it from the repo root.
  local root; root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  local win="$root/.venv-pmoves/Scripts/python.exe"
  local nix="$root/.venv-pmoves/bin/python"
  local interp="" layout="" m

  echo "🔍 Bringup interpreter (advisory)"

  # Run the candidate rather than test for it. MSYS reports any file ending
  # .exe as executable regardless of content, so -x cannot tell a real
  # interpreter from an interrupted install.
  for c in "$win:Windows (Scripts/python.exe)" "$nix:POSIX (bin/python)"; do
    if "${c%%:*}" -c pass >/dev/null 2>&1; then interp="${c%%:*}"; layout="${c#*:}"; break; fi
  done

  if [[ -z "$interp" ]]; then
    printf "  ❌ %-22s not provisioned or not runnable (both layouts probed)\n" "bringup env"
    echo "     Remedy: make -C pmoves venv-bringup"
    echo
    ENV_MISSING=1; ENV_GAPS="the interpreter itself"
    return 0
  fi

  printf "  ✅ %-22s %s\n" "bringup env" "$layout"
  [[ "$QUIET" -eq 0 ]] && printf "  %-25s %s\n" "" "$("$interp" -c 'import sys;print(sys.version.split()[0])' 2>/dev/null || echo '?')"

  local gaps=()
  for m in "${BRINGUP_MODULES[@]}"; do
    # -I keeps the cwd OFF sys.path. Without it the probe is cwd-sensitive and
    # lies: pmoves/ contains a `nats/` directory that shadows the real nats-py
    # package, so a plain `import nats` PASSES from pmoves/ and FAILS from the
    # repo root for the same interpreter.
    if "$interp" -I -c "import $m" >/dev/null 2>&1; then
      [[ "$QUIET" -eq 0 ]] && printf "  ✅ %-22s importable\n" "$m"
    else
      printf "  ❌ %-22s NOT importable by the bringup interpreter\n" "$m"
      gaps+=("$m")
    fi
  done

  if [[ ${#gaps[@]} -gt 0 ]]; then
    ENV_MISSING=$((ENV_MISSING + ${#gaps[@]}))
    ENV_GAPS="${gaps[*]}"
    echo "     Remedy: make -C pmoves venv-bringup"
  fi
  echo
}

# ── Stale-session PATH banner (Windows) ──────────────────────────────────────
# Deliberately a banner, not a per-binary index. Attributing a specific missing
# binary to a specific stale directory needs a directory walk whose cost and
# correctness problems outweigh its value; the banner is what actually explains
# the symptom. Two forks total: one powershell, one cygpath for the whole PATH.
path_staleness_banner() {
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) ;; *) return 0 ;; esac
  command -v powershell.exe >/dev/null 2>&1 || return 0
  command -v cygpath >/dev/null 2>&1 || return 0

  local ps_cmd persisted live_w stale=() d
  ps_cmd='$m=[Environment]::GetEnvironmentVariable("Path","Machine");'
  ps_cmd+='$u=[Environment]::GetEnvironmentVariable("Path","User");'
  ps_cmd+='(($m+";"+$u) -split ";") | Where-Object { $_.Trim() -ne "" }'
  persisted=$(powershell.exe -NoProfile -Command "$ps_cmd" 2>/dev/null | tr -d '\r')
  [[ -z "$persisted" ]] && return 0

  # One cygpath for the entire live PATH. Everything after this is bash
  # builtins: normalising and comparing per entry with sed/tr/grep costs three
  # forks per directory, and this node has 94 persisted entries — measured at
  # 6.7s, which is most of the runtime and the reason an earlier version of
  # this function was too slow to keep on the bringup path.
  live_w=$(printf '%s' "$PATH" | tr ':' '\n' | cygpath -w -f - 2>/dev/null)

  local -A live_set=()
  local w key
  while IFS= read -r w; do
    [[ -z "$w" ]] && continue
    while [[ "$w" == *[\\/] ]]; do w="${w%?}"; done
    live_set["${w,,}"]=1
  done <<<"$live_w"

  while IFS= read -r d; do
    [[ -z "$d" ]] && continue
    key="$d"
    while [[ "$key" == *[\\/] ]]; do key="${key%?}"; done
    [[ -n "${live_set[${key,,}]:-}" ]] || stale+=("$d")
  done <<<"$persisted"

  [[ ${#stale[@]} -eq 0 ]] && return 0

  echo "⚠️  Stale session PATH — ${#stale[@]} persisted director$([[ ${#stale[@]} -eq 1 ]] && echo y || echo ies) not visible to this shell:"
  printf '     %s\n' "${stale[@]}"
  echo "     A tool installed in one of these reads as MISSING above even though"
  echo "     it is present. Reinstalling cannot fix that; a new terminal can."
  echo
}

virtualenv_report() {
  [[ -z "${VIRTUAL_ENV:-}" ]] && return 0
  echo "ℹ️  VIRTUAL_ENV active: ${VIRTUAL_ENV}"
  echo "     python resolves to: $(command -v python 2>/dev/null || echo '<none>')"
  echo "     Run 'deactivate' if that is not the interpreter you meant."
  echo
}

# ── Run ──────────────────────────────────────────────────────────────────────
req_missing=0
agent_missing=0

if [[ "$TIER" == "bringup" || "$TIER" == "all" ]]; then
  check_tier "Bringup prereqs (required)" REQUIRED
  req_missing=$TIER_MISSING
fi

if [[ "$TIER" == "agent" || "$TIER" == "all" ]]; then
  check_tier "Agent CLI contract (advisory)" AGENT
  agent_missing=$TIER_MISSING
fi

if [[ "$TIER" == "env" || "$TIER" == "all" ]]; then
  env_tier_report
fi

# Only worth the two forks if something failed to resolve.
[[ $((req_missing + agent_missing)) -gt 0 ]] && path_staleness_banner
virtualenv_report

rc=0

if [[ "$req_missing" -gt 0 ]]; then
  echo "❌ $req_missing required prereq(s) missing. Install with the hint above and re-run."
  echo "   Then: make -C pmoves venv-bringup"
  rc=1
fi

if [[ "$agent_missing" -gt 0 ]]; then
  echo "⚠️  $agent_missing agent-CLI gap(s) — see the unlocks line for what each one costs."
  [[ "$STRICT" -eq 1 ]] && rc=1
fi

if [[ "$ENV_MISSING" -gt 0 ]]; then
  # Name what is actually missing. A fixed epilogue that always blames
  # sign-trail/yaml is wrong whenever the gap is something else, and this file
  # asks callers to trust its unlocks lines.
  echo "⚠️  bringup interpreter gap(s): ${ENV_GAPS}"
  echo "   Make targets that import these through pmoves/tools/*.py will fail or degrade."
  case " $ENV_GAPS " in
    *" yaml "*|*"the interpreter itself"*)
      echo "   yaml specifically: sign-trail cannot resolve the agent identity and"
      echo "   signs with a FALLBACK presentation that is NOT the registered identity." ;;
  esac
  [[ "$STRICT" -eq 1 ]] && rc=1
fi

if [[ $((req_missing + agent_missing + ENV_MISSING)) -eq 0 ]]; then
  echo "✅ All checked prereqs present."
fi

exit "$rc"
