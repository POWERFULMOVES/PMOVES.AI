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

# Bash 4+ is required: associative arrays (already used by the original version
# of this script), namerefs, and ${var,,}. Stock macOS still ships Bash 3.2 as
# /bin/bash, and pmoves/AGENTS.md documents a macOS bootstrap, so this would
# otherwise fail with a parse error that names none of the above.
#
# Re-exec under a newer bash when one is installed (Homebrew puts it in
# /opt/homebrew/bin or /usr/local/bin and does NOT replace /bin/bash), so the
# common macOS case just works instead of erroring.
if [[ -z "${BASH_VERSINFO:-}" || "${BASH_VERSINFO[0]}" -lt 4 ]]; then
  # One-shot: never re-exec twice. Without this, any situation where the
  # re-exec target still fails the version test loops forever spawning shells.
  if [[ -z "${PMOVES_PREREQ_REEXEC:-}" ]]; then
    for _cand in /opt/homebrew/bin/bash /usr/local/bin/bash /usr/bin/bash; do
      if [[ -x "$_cand" ]] && [[ "$("$_cand" -c 'echo ${BASH_VERSINFO[0]}' 2>/dev/null || echo 0)" -ge 4 ]]; then
        PMOVES_PREREQ_REEXEC=1 exec "$_cand" "$0" "$@"
      fi
    done
  fi
  echo "check_prereqs.sh: needs bash 4+ (found ${BASH_VERSION:-unknown, likely not bash})." >&2
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Darwin)
      echo "  macOS ships bash 3.2 as /bin/bash and Homebrew does not replace it." >&2
      echo "    brew install bash" >&2
      echo "    \"\$(brew --prefix)/bin/bash\" pmoves/scripts/check_prereqs.sh" >&2 ;;
    Linux)
      echo "  Most distros ship bash 5. Hitting this usually means either a minimal" >&2
      echo "  image (Alpine/BusyBox provide ash, not bash) or invocation via 'sh'." >&2
      echo "    Debian/Ubuntu: apt-get install -y bash" >&2
      echo "    Alpine:        apk add bash" >&2
      echo "    Then run it as 'bash <script>', not 'sh <script>'." >&2 ;;
    MINGW*|MSYS*|CYGWIN*)
      echo "  Git Bash ships bash 4.4+, so this is unexpected here. Check that the" >&2
      echo "  script is not being run through a stripped-down sh on PATH." >&2
      echo "    \"C:/Program Files/Git/bin/bash.exe\" pmoves/scripts/check_prereqs.sh" >&2 ;;
    *)
      echo "  Install bash 4 or newer and invoke the script with it directly." >&2 ;;
  esac
  echo >&2
  echo "  Environment setup across Windows / WSL / Linux / macOS:" >&2
  echo "    pmoves/docs/operations/LOCAL_TOOLING_REFERENCE.md" >&2
  echo "    make -C pmoves venv-bringup   # provisions .venv-pmoves + tool deps" >&2
  exit 2
fi

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

# Repo root, from BASH_SOURCE rather than cwd: the Make target runs this from
# inside pmoves/ while an operator runs it from the repo root.
PMOVES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Some agent-tier tools are installed INTO the bringup environment rather than
# onto PATH -- glances is, via `venv-bringup`. Reporting those as plain MISSING
# makes the advertised remedy look like it failed: you run venv-bringup, it
# succeeds, and the next check-prereqs-strict still exits non-zero telling you
# to install the thing you just installed. Look in the environment too, and
# distinguish "absent" from "present but not on PATH" -- different remedies.
find_in_bringup_env() {
  local b="$1" d f
  for d in "$PMOVES_DIR/.venv-pmoves/Scripts" "$PMOVES_DIR/.venv-pmoves/bin"; do
    for f in "$d/$b" "$d/$b.exe"; do
      [[ -f "$f" ]] && { printf '%s' "$f"; return 0; }
    done
  done
  return 1
}

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
  local bin version found_at
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
    elif found_at=$(find_in_bringup_env "$bin"); then
      # Present, just not reachable from this shell. An activation gap, not a
      # missing package -- and reinstalling is the wrong remedy.
      TIER_MISSING=$((TIER_MISSING+1))
      printf "  ⚠️  %-10s in the bringup env but NOT on PATH\n" "$bin"
      printf "     %-10s at: %s\n" "" "$found_at"
      printf "     %-10s activate the env or call it by path — reinstalling will not help\n" ""
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

  # Probe the interpreter Make will ACTUALLY use, when it tells us which that
  # is. The Make targets export PMOVES_PREREQ_PY="$(PRECHECK_PY)", so an
  # operator on the documented Conda bootstrap (pmoves/AGENTS.md: "Preferred
  # Python: Conda 3.11+") or a PYTHON=/custom pin gets that interpreter checked
  # rather than a .venv-pmoves that may not exist. Probing only .venv-pmoves
  # would fail a healthy Conda setup and, worse, could pass while the
  # interpreter Make really invokes lacks the modules -- an instrument
  # reporting on something other than what runs.
  if [[ -n "${PMOVES_PREREQ_PY:-}" ]]; then
    # May be multi-word ("py -3"); word-splitting is intended here.
    # shellcheck disable=SC2086
    if ${PMOVES_PREREQ_PY} -c pass >/dev/null 2>&1; then
      interp="${PMOVES_PREREQ_PY}"; layout="as selected by make (PRECHECK_PY)"
    fi
  fi

  # Run the candidate rather than test for it. MSYS reports any file ending
  # .exe as executable regardless of content, so -x cannot tell a real
  # interpreter from an interrupted install.
  if [[ -z "$interp" ]]; then
    for c in "$win:Windows (Scripts/python.exe)" "$nix:POSIX (bin/python)"; do
      if "${c%%:*}" -c pass >/dev/null 2>&1; then interp="${c%%:*}"; layout="${c#*:}"; break; fi
    done
  fi

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
    # shellcheck disable=SC2086  # interp may be "py -3"; splitting is intended
    if ${interp} -I -c "import $m" >/dev/null 2>&1; then
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
