---
description: Mint a new PMOVES skill through Archon — scaffold SKILL.md, lint, register, publish archon.mint.skill.v1.
---

Mint a new composable skill into the PMOVES skills constellation. Mirrors `/archon:mint-agent` for skills.

## Usage

Invoke when the operator says "mint a skill", "scaffold a SKILL.md", or "register a composable skill". Produces a SKILL.md under `.claude/skills/<name>/`, runs the skill linter, registers via Archon (when ready), and publishes the NATS mint event.

## Implementation

### Step 1 — Collect the manifest

Ask the operator for:

- `skill-name` — kebab-case (e.g. `pmoves-room-rotator`).
- `description` — single sentence beginning with an action verb; this becomes the frontmatter `description`.
- `user-invocable?` — boolean. If false, set frontmatter `user-invocable: false` (Claude-only).
- `owning-persona` — accountable agent or human.
- Optional: `tools`, `dependencies` (other skills it composes with).

Validate uniqueness:

```bash
test ! -d ".claude/skills/<skill-name>" || { echo "skill exists"; exit 1; }
```

### Step 2 — Scaffold the skill

Create `.claude/skills/<skill-name>/SKILL.md`:

```markdown
---
name: <skill-name>
description: <description>
user-invocable: <true|false>
owning_persona: <owning-persona>
minted_at: <YYYY-MM-DD>
---

# <Skill-Name>

## When to invoke

<one paragraph trigger conditions>

## Inputs

<bullet list>

## Outputs

<bullet list>

## Implementation

<script reference or inline steps>
```

If the skill ships a script, also scaffold `.claude/skills/<skill-name>/scripts/<entry>.sh` (or `.py`) with a shebang and `set -euo pipefail`.

### Step 3 — Lint

Run frontmatter + structure checks:

```bash
# Frontmatter present
head -1 .claude/skills/<skill-name>/SKILL.md | grep -q '^---$' || echo "FAIL: missing frontmatter"
# Description starts with verb (heuristic)
grep -E '^description: [A-Z][a-z]+ ' .claude/skills/<skill-name>/SKILL.md || echo "WARN: description should start with an action verb"
# Required sections
for s in "When to invoke" "Inputs" "Outputs" "Implementation"; do
  grep -q "^## $s$" .claude/skills/<skill-name>/SKILL.md || echo "FAIL: missing section '$s'"
done
```

Block on any FAIL.

### Step 4 — Register through Archon

Contract for the future `archon:create-skill` MCP tool:

```jsonc
{
  "name": "create-skill",
  "input": {
    "skill_name": "<skill-name>",
    "description": "<description>",
    "user_invocable": <bool>,
    "path": ".claude/skills/<skill-name>/SKILL.md"
  },
  "output": { "skill_id": "<uuid>", "registry_url": "<url>" }
}
```

Until the MCP tool ships, optionally `curl -sf -X POST http://localhost:8091/api/skills` with the manifest. If the endpoint is unavailable, stash the manifest under `/tmp/skill-manifest.json` and continue.

### Step 5 — Publish NATS mint event

```jsonc
{
  "subject": "archon.mint.skill.v1",
  "payload": {
    "skill_id": "<uuid|null>",
    "skill_name": "<skill-name>",
    "path": ".claude/skills/<skill-name>/SKILL.md",
    "user_invocable": <bool>,
    "owning_persona": "<owning-persona>",
    "ts": "<RFC3339>"
  }
}
```

Publish via `pmoves-nats-mcp` `nats_publish` tool if configured, otherwise print the payload + the `nats pub archon.mint.skill.v1 ...` fallback.

### Step 6 — Cross-link

Append a row to `skills/README.md` (Status: provisional) so the constellation surface reflects the new skill.

## Notes

- Wave-0 Task 9 in the gap-fill roadmap.
- Wave-1 dependency: Supabase `archon_minted_artifacts` table (W1.10).
- Wave-2 dependency: `archon.mint.skill.v1` publishers on the bus (W2.1).
- Companion: `/archon:mint-agent` for agents, `/archon:creator-onboard` for human creators.
