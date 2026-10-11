# Skills projection at launch — handoff

Lane: `feat/skills-projection-at-launch` (5090-CLAUDE, claim filed 2026-10-11). Approved by the operator on 2026-10-11 against the recommendation in `pmoves/docs/TAC/TAC_HARNESS_OVERLAY_MAP.md` § "Skills seam" (#3347).

Operator canon, 2026-10-11 (verbatim): "parrity across AGInTZ skills cant only work for one" and, on the theme work, "a lot was done howeever not wired includeing the themes glyphs and all the customization work that went in which should load with claude-pmoves".

## What was measured (2026-10-11, 5090)

| Harness | Reads | Before | After one projection |
|---|---|---|---|
| Claude Code | `.claude/skills/` | 36 (canonical) | 36 |
| Codex, OpenCode, Kimi Code | `.agents/skills/` | dir absent | 36 |
| Kilo | `.kilocode/skills/` | 24 Kilo-only | 24 + 36 |
| Crush | `.crush/skills/` | dir absent | 36 |
| Hermes | `.hermes/skills/` | dir absent | 36 |

`make -C pmoves skills-parity` (lands with #3347) read `PARITY GAP: 216 missing placements across 6 harnesses` before and `PARITY OK` after. The projector is the PMOVES-skills CLI (`skills/PMOVES-skills`, fork of vercel-labs/skills), run as `add ./.claude/skills -s '*' --copy -y` with one `-a` per harness; `-a` does not take a comma list (measured: "Invalid agents: codex,opencode,...").

## What lands here

- `pmoves/scripts/pm-skills-project.sh` — `pm_skills_project ROOT [FORCE]`. Fail-open, loud. Stamp at `.agents/.pmoves-skills-stamp` makes the call free when nothing under `.claude/skills` changed. CLI resolution: `PM_SKILLS_CLI` (tests) → built local fork (`skills/PMOVES-skills/dist` + `bin/cli.mjs`) → `npx -y skills` → WARN naming the build route. Telemetry disabled (`DISABLE_TELEMETRY=1`, `DO_NOT_TRACK=1`).
- `pmoves/scripts/pm-theme-banner.sh` — `pm_theme_banner ROOT AGENT_ID [PYTHON...]`. Renders `agent_terminal_theme.py --agent <card id> --banner` to stderr. Fail-open. Measured on 5090: `theme=rendered for 5090-claude`.
- `make -C pmoves skills-project` (`FORCE=1` to ignore the stamp). Exit 1 only when the projection did not happen, so CI can gate on it later.
- `.gitignore`: `.kilocode/skills/*` with `!.kilocode/skills/kilocode-*/` (Kilo's own 24 skills stay tracked), `.crush/skills/`, `.hermes/skills/`, `skills-lock.json`, `.agents/skills/` and the stamp. (`.agents/` is not ignored on main; only the projection paths under it are.)
- `pmoves/tests/test_pm_skills_project.py` — hermetic contract tests (stub CLI): agent flags, `--copy`, cwd, telemetry env, stamp skip/rerun/FORCE, failure is loud and leaves no stamp, no-CLI names the build route, and the harness list is pinned to `skills_parity.py` when present.

## What the operator applies (launcher Known Road)

`pmoves/scripts/*-pmoves*` and `deploy/provision/*-pmoves.sh` are `readOnlyPaths`; the grant domain is `launcher` and grants are operator-reserved. The hookups are therefore staged as patches, generated from the launchers at this branch's base and validated with `git apply --check` and `bash -n` on the patched copies:

| Patch | Touches | Where the block sits |
|---|---|---|
| `patches/SKILLS_PROJECTION_launchers.patch` | `codex-pmoves.sh`, `kilo-pmoves.sh`, `kimi-pmoves.sh`, `crush-pmoves`, `hermes-pmoves`, `claude-pmoves.sh` (all `pmoves/scripts/`) | after the identity/cipher carry block, before the harness-specific config and `exec` |
| `patches/THEME_BANNER_claude_launcher.patch` | `pmoves/scripts/claude-pmoves.sh` | after the BRV block, before `pm_ident_prompt_args`; uses `PM_IDENT_CIPHER_ID` and the resolved `IDENT_PY` |

```bash
KNOWN_ROAD=launcher:pr:<this PR> git apply pmoves/docs/handoffs/patches/SKILLS_PROJECTION_launchers.patch
KNOWN_ROAD=launcher:pr:<this PR> git apply pmoves/docs/handoffs/patches/THEME_BANNER_claude_launcher.patch
bash -n pmoves/scripts/*-pmoves.sh pmoves/scripts/crush-pmoves pmoves/scripts/hermes-pmoves
```

The patches are LF, generated from the index copies. `crush-pmoves` and `hermes-pmoves` are `text=auto`, so a Windows worktree holds them as CRLF: apply there with `git apply --ignore-whitespace`, or apply on a Linux node. `kimi-pmoves.sh` and `kilo-pmoves.sh` are also changed by #3325; apply this patch after #3325 merges and regenerate the hunk if the context moved (the block is self-contained; only its anchor line matters). The generated trio under `deploy/provision/` is NOT patched: when the hand-written and generated launchers converge, the generator template is the place for the block, not a second copy.

## Verify after applying

```bash
make -C pmoves skills-project FORCE=1      # [skills-project] skills=projected (36 skills -> codex, opencode, kimi-code-cli, kilo, crush, hermes-agent)
make -C pmoves skills-parity               # PARITY OK (after #3347)
claude-pmoves                              # stderr shows the identity banner, then [claude-pmoves] skills=... / theme=...
```

## Not done here

- Projection into the user-level dirs (`~/.agents/skills`, `~/.config/opencode/skills`, ...): project-level only; a session started outside the repo keeps Claude-only skills.
- `.kimi/skills/pmoves-kimi-bootstrap` (archived kimi-cli surface) is untouched; Kimi Code reads `.agents/skills/`.
- The skills CLI writes `skills-lock.json` at the repo root; it is ignored, not consumed. `experimental_install` could restore from it on a fresh node; not wired.
