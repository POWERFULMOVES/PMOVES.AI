# PMOVES-skills review

**Submodule:** [skills/PMOVES-skills/](https://github.com/POWERFULMOVES/PMOVES-skills) (PMOVES fork of [vercel-labs/skills](https://github.com/vercel-labs/skills))
**Pin:** c6f69c631292444cc541ac6d91e2226b0ff247da
**Recentering note:** was `MiniMax-AI/skills`, moved to `vercel-labs/skills` in August 2026. The pre-recenter URL (`POWERFULMOVES/Pmoves-Minimax-skills`) is preserved as a deprecated reference, not a separate submodule entry. See `skills/README.md` for the recentering note.

The fold-in PR1 (PR #2586, 2026-08-17) added this submodule to the PMOVES.AI skills constellation as the post-recenter home of the open-skills-ecosystem library. This review audits what it brings, what's worth pulling into our catalog, and what's worth leaving alone.

## What's in the submodule

The submodule is the upstream `vercel-labs/skills` repo, which is the package manager for the open agent skills ecosystem. It contains:

1. **The `skills` CLI** (TypeScript/Bun, ships as `bin/skills`): a package manager for skills. Three commands:
   - `npx skills find [query] [--owner <owner>]` — search for skills by keyword
   - `npx skills add <package>` — install a skill from a GitHub URL, owner/repo shorthand, or local path
   - `npx skills update` — update all installed skills
2. **One bundled skill:** `skills/find-skills/SKILL.md` (the meta-skill that helps an agent decide "is there a skill for X?" and run the find command).
3. **The leaderboard** at [skills.sh](https://skills.sh/) — a community ranking of skills by total installs.

The CLI is engine-agnostic. It supports OpenCode, Claude Code, Codex, Cursor, and 72 more agents. The relevant fact for PMOVES is that it works with our existing agent surfaces without any PMOVES-side adapter.

## What find-skills gives us

The find-skills skill is a meta-skill — it doesn't do work itself, it helps an agent decide whether a more specialized skill exists. The pattern:

1. **User asks "how do I do X?"** — the agent loads find-skills, checks the leaderboard, runs `npx skills find X` if needed, and either installs a relevant skill or proceeds without.
2. **User asks "find a skill for X"** — same flow, but with explicit intent to install.
3. **User wants to extend capabilities** — the agent uses find-skills to surface candidates.

For PMOVES operators, the load-bearing use case is #1. An agent in a Mavis session that gets a request like "build me a podcast from these audio files" should be able to surface any audio-pipeline skills that exist in the open ecosystem, rather than hand-rolling from scratch. The `npx skills find` query against a `--owner` filter (`--owner POWERFULMOVES`) scopes the search to our forks first.

## What's worth pulling into the PMOVES catalog

Three things, in priority order:

### 1. The find-skills skill itself — yes, add to skill-pairings

`pmoves/configs/skill-pairings.yaml` has a `skill_sources` block (per the CLI tools registry PR #2599) that lets BoTZ pipelines surface tools to agents. Adding `find-skills` there means a BoTZ-driven agent on the sidecar lane can offer the user "I see there's a skill for X, want me to install it?" instead of doing the work from scratch.

The wiring is a one-liner:

```yaml
skill_sources:
  # ... existing entries ...
  find-skills:
    type: meta-skill
    path: skills/PMOVES-skills/skills/find-skills/SKILL.md
    note: "Meta-skill for discovering open-ecosystem skills. Engine-agnostic."
```

This is a low-risk, additive change. Recommendation: do it as part of the next BoTZ skill-pairings update, not in this PR.

### 2. The `skills` CLI as a host CLI — yes, add to cli_tools.yaml

`pmoves/configs/cli_tools.yaml` (the canonical CLI inventory, added by PR #2599) has a `host_clis` block that the doctor (`make -C pmoves cli-check`) validates. The `npx skills` invocation is the right host-CLI surface for the find-skills skill. Adding it:

```yaml
host_clis:
  # ... existing entries ...
  skills:
    purpose: "Open skills ecosystem package manager (vercel-labs/skills CLI, via npx)"
    required: false
    install:
      macos: "npm install -g skills"
      linux: "npm install -g skills"
      windows: "npm install -g skills"
    check: "npx skills --version"
```

This is the second half of the wire-up: the skill needs a CLI to actually execute. Same recommendation as #1: do it in the next BoTZ/CLI registry update, not this PR.

### 3. The PMOVES-specific skills under `--owner POWERFULMOVES` — flag in the agent prompt

The find-skills skill, when used by a PMOVES agent, should default to `--owner POWERFULMOVES` first (so we surface our own forks before the open ecosystem). This is a one-line change to the find-skills SKILL.md invocation example, but it's a behavioral default that should be encoded in the PMOVES-side wrapper, not in the upstream SKILL.md. Recommendation: leave the upstream SKILL.md alone (we don't own it), and document the default in `pmoves/docs/skills/PMOVES_SKILLS_REVIEW.md` (this doc).

## What to leave alone

- **The `skills/find-skills/SKILL.md` content** — it's upstream, it works, and editing it would create a fork drift. We document our override defaults here instead.
- **The `skills` CLI source** — no PMOVES-side patches. If we ever need a fork-specific behavior, add it as a wrapper in `pmoves/tools/`, not as a submodule edit.
- **The pre-recenter URL** (`POWERFULMOVES/Pmoves-Minimax-skills`) — preserved as a deprecated reference per the `skills/README.md` Recentering note. Do not add a separate submodule entry for it; the fold-in PR1 deliberately chose one submodule over two to avoid splitting the recenter story.

## Skill-pairing manifest delta (proposed, not applied)

For visibility, here's the full proposed delta to `pmoves/configs/skill-pairings.yaml` if the operator wants to land it in a follow-up:

```yaml
# Existing entries preserved verbatim; this is the addition only.
skill_sources:
  find-skills:
    type: meta-skill
    path: skills/PMOVES-skills/skills/find-skills/SKILL.md
    note: "Meta-skill for discovering open-ecosystem skills. Default scope: --owner POWERFULMOVES first, then unfiltered."
```

And the `host_clis` addition in `pmoves/configs/cli_tools.yaml`:

```yaml
host_clis:
  skills:
    purpose: "Open skills ecosystem package manager (vercel-labs/skills CLI, via npx)"
    required: false
    install:
      macos: "npm install -g skills"
      linux: "npm install -g skills"
      windows: "npm install -g skills"
    check: "npx skills --version"
```

These are both additive and don't conflict with anything in the current manifests. They're documented here for the operator to land in a follow-up if the BoTZ skill-pairings lane is in scope.

## Reference

- Submodule: `skills/PMOVES-skills/` (PMOVES fork of vercel-labs/skills)
- Submodule pin: `c6f69c631292444cc541ac6d91e2226b0ff247da`
- Recentering context: `skills/README.md` (Recentering note, 2026-08-17)
- Submodules doc: `.claude/context/submodules.md` line 112
- Pre-recenter URL (deprecated): `POWERFULMOVES/Pmoves-Minimax-skills`
- Fold-in PR: PR #2586 (Mavis, 2026-08-17)
- Upstream repo: https://github.com/vercel-labs/skills
- Skills leaderboard: https://skills.sh/
