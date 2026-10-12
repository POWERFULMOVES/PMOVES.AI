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
# THE STAMP IS A CONTENT FINGERPRINT, NOT AN MTIME
# -----------------------------------------------
# Review finding on #3351 (kilo, 2026-10-11): an mtime stamp (`find -newer`)
# sees files that appeared or changed and is blind to files that vanished, so
# a deleted skill would keep its ghost copies in every harness dir forever.
# The stamp therefore records a checksum over every file under .claude/skills
# (relative path + cksum), plus the list of skill names that were projected.
# Any difference re-runs the CLI; names that were projected last time and no
# longer exist in the source are removed from each projection dir, so the
# projections track deletions the same way they track edits.
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
#   PM_SKILLS_OK     1 projected, 2 skipped (fingerprint unchanged since the
#                    last projection), 0 not projected (no CLI, or it failed)
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
# Project-level dirs those agents read (skills/PMOVES-skills/src/agents.ts;
# the same table pmoves/tools/skills_parity.py pins). Only names this script
# projected are ever removed from them.
PM_SKILLS_DIRS=".agents/skills .kilocode/skills .crush/skills .hermes/skills"
PM_SKILLS_STAMP_REL=".agents/.pmoves-skills-stamp"

# Checksum over every file under the source tree: "relative-path crc size" per
# file, sorted, then one cksum over that listing. cksum is POSIX, so this runs
# wherever the launchers do (Git Bash, Linux, macOS).
pm_skills_fingerprint() {
  local src="$1" f
  find "$src" -type f -print 2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
    printf '%s %s\n' "${f#"$src"/}" "$(cksum < "$f")"
  done | cksum | tr -d ' \t'
}

# One skill name per line (directories holding a SKILL.md), sorted.
pm_skills_names() {
  local src="$1" f
  find "$src" -mindepth 2 -maxdepth 2 -name SKILL.md -print 2>/dev/null | while IFS= read -r f; do
    f="${f%/SKILL.md}"
    printf '%s\n' "${f##*/}"
  done | LC_ALL=C sort
}

pm_skills_project() {
  local root="$1" force="${2:-0}"
  PM_SKILLS_OK=0
  PM_SKILLS_LINE=""

  local src="$root/.claude/skills" stamp="$root/$PM_SKILLS_STAMP_REL"
  if [ ! -d "$src" ]; then
    PM_SKILLS_LINE="skills=SKIP (no $src)"
    return 0
  fi

  local fp names
  fp="$(pm_skills_fingerprint "$src")"
  names="$(pm_skills_names "$src")"

  local old_fp="" old_names=""
  if [ -f "$stamp" ]; then
    old_fp="$(head -n 1 "$stamp" 2>/dev/null)"
    old_names="$(tail -n +2 "$stamp" 2>/dev/null)"
  fi

  if [ "$force" != "1" ] && [ -n "$old_fp" ] && [ "$old_fp" = "$fp" ]; then
    PM_SKILLS_OK=2
    PM_SKILLS_LINE="skills=fresh (.claude/skills unchanged since the last projection, $PM_SKILLS_STAMP_REL)"
    return 0
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
    # Sync removals: a name we projected last time that is gone from the
    # source loses its copy in every projection dir. Nothing else is touched.
    local removed=0 name dir
    if [ -n "$old_names" ]; then
      while IFS= read -r name; do
        [ -n "$name" ] || continue
        if printf '%s\n' "$names" | grep -qx -- "$name"; then
          continue
        fi
        for dir in $PM_SKILLS_DIRS; do
          if [ -d "$root/$dir/$name" ]; then
            rm -r -- "$root/$dir/$name" 2>/dev/null && removed=$((removed + 1))
          fi
        done
      done <<EOF
$old_names
EOF
    fi
    mkdir -p "$root/.agents" 2>/dev/null && printf '%s\n%s\n' "$fp" "$names" >"$stamp"
    local n
    n="$(printf '%s\n' "$names" | grep -c . | tr -d ' ')"
    PM_SKILLS_OK=1
    PM_SKILLS_LINE="skills=projected (${n} skills -> ${PM_SKILLS_AGENTS// /, }"
    if [ "$removed" -gt 0 ]; then
      PM_SKILLS_LINE="${PM_SKILLS_LINE}; ${removed} stale copies removed"
    fi
    PM_SKILLS_LINE="${PM_SKILLS_LINE})"
    rm "$log" 2>/dev/null || true
  else
    PM_SKILLS_LINE="WARN: skills=FAILED -- projection did not complete; the other harnesses keep their last projection (log: $log)"
  fi
  return 0
}
