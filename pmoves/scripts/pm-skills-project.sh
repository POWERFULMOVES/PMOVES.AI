#!/usr/bin/env bash
# pm-skills-project.sh — project .claude/skills into every harness's skills dir.
# ===========================================================================
# WHY THIS EXISTS
# ---------------
# Operator canon, 2026-10-11 (verbatim): "parrity across AGInTZ skills cant
# only work for one". Measured the same day with `make -C pmoves skills-parity`:
# 36 skills under .claude/skills/ reached ONE of seven harnesses. Codex,
# OpenCode and Kimi Code read `.agents/skills/`; Kilo reads `.kilocode/skills/`;
# Crush `.crush/skills/`; Hermes `.hermes/skills/`. Claude Code reads only its
# own directory, so parity needs a projection step in every direction.
#
# The projector is the PMOVES-skills CLI (fork of vercel-labs/skills), which
# already knows every harness's directory (`src/agents.ts`). Projections are
# COPIES and are gitignored: git symlinks fail on Windows checkouts (measured
# three times on 2026-10-11) and tracked copies drift. Each launcher calls this
# once at launch; a stamp file makes the call free when nothing changed.
#
# THE CONTRACT
# ------------
# pm_skills_project ROOT [FORCE]
#
#   ALWAYS returns 0. A failed projection costs the other harnesses their
#   skills for this session, not the launch (same doctrine as pm-brv-check.sh:
#   losing it must never cost you the launch). Loud, never silent.
#
# On return, ALWAYS set:
#   PM_SKILLS_OK     1 projected, 2 skipped (stamp newer than every source
#                    file), 0 not projected (no CLI, or the CLI failed)
#   PM_SKILLS_LINE   one line for stderr, prefixed by the caller
#
# Overrides:
#   PM_SKILLS_CLI    path to a CLI to run instead of the discovered one (tests)
#   FORCE=1 (2nd arg) ignore the stamp
#
# CLI RESOLUTION, in order: PM_SKILLS_CLI; the built local fork
# (skills/PMOVES-skills/dist present, run through bin/cli.mjs); `npx -y skills`
# (upstream package, same agent table). No node and no npx -> WARN, OK=0.

PM_SKILLS_AGENTS="codex opencode kimi-code-cli kilo crush hermes-agent"
PM_SKILLS_STAMP_REL=".agents/.pmoves-skills-stamp"

pm_skills_project() {
  local root="$1" force="${2:-0}"
  PM_SKILLS_OK=0
  PM_SKILLS_LINE=""

  local src="$root/.claude/skills" stamp="$root/$PM_SKILLS_STAMP_REL"
  if [ ! -d "$src" ]; then
    PM_SKILLS_LINE="skills=SKIP (no $src)"
    return 0
  fi

  if [ "$force" != "1" ] && [ -f "$stamp" ]; then
    local newer
    newer="$(find "$src" -newer "$stamp" -print 2>/dev/null | head -n 1)"
    if [ -z "$newer" ]; then
      PM_SKILLS_OK=2
      PM_SKILLS_LINE="skills=fresh (nothing under .claude/skills newer than $PM_SKILLS_STAMP_REL)"
      return 0
    fi
  fi

  local -a cmd
  if [ -n "${PM_SKILLS_CLI:-}" ]; then
    cmd=("$PM_SKILLS_CLI")
  elif [ -f "$root/skills/PMOVES-skills/dist/cli.mjs" ] && command -v node >/dev/null 2>&1; then
    cmd=(node "$root/skills/PMOVES-skills/bin/cli.mjs")
  elif command -v npx >/dev/null 2>&1; then
    cmd=(npx -y skills)
  else
    PM_SKILLS_LINE="WARN: skills=NO-CLI -- neither a built skills/PMOVES-skills (pnpm -C skills/PMOVES-skills install && pnpm -C skills/PMOVES-skills build) nor npx on PATH; the other harnesses keep their last projection"
    return 0
  fi

  local -a args=(add ./.claude/skills -s '*' -y --copy)
  local agent
  for agent in $PM_SKILLS_AGENTS; do
    args+=(-a "$agent")
  done

  local log
  log="$(mktemp 2>/dev/null || printf '%s/pm-skills-project.%s.log' "${TMPDIR:-/tmp}" "$$")"
  if (cd "$root" && DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 "${cmd[@]}" "${args[@]}" >"$log" 2>&1); then
    mkdir -p "$root/.agents" 2>/dev/null && : >"$stamp"
    local n
    n="$(find "$src" -mindepth 2 -maxdepth 2 -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
    PM_SKILLS_OK=1
    PM_SKILLS_LINE="skills=projected (${n} skills -> ${PM_SKILLS_AGENTS// /, })"
    rm "$log" 2>/dev/null || true
  else
    PM_SKILLS_LINE="WARN: skills=FAILED -- projection did not complete; the other harnesses keep their last projection (log: $log)"
  fi
  return 0
}
