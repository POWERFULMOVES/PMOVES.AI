# claude_settings — Claude Code backend templates

These templates are written to `~/.claude/settings.json` by `pmoves-mini claude-backend set <backend>`.
They define which model provider Claude Code launches with on the operator's host.

## Templates

| File | Backend | What it does |
|---|---|---|
| `anthropic.json` | `anthropic` | The pre-2026-09-10 state. No `ANTHROPIC_*` env overrides; default Anthropic model picker. Claude Code uses the operator's own Anthropic API key. |
| `minimax.json` | `minimax` | The current (2026-09-25) state. `ANTHROPIC_MODEL=MiniMax-M3[1m]` + matching Sonnet/Opus/Haiku defaults + a `modelPicker.replaceBuiltInOptions: true` listing only MiniMax models. Routes Claude Code through MiniMax endpoints. |

## Switching

```
pmoves-mini claude-backend show              # print current state
pmoves-mini claude-backend set anthropic     # restore Anthropic routing
pmoves-mini claude-backend set minimax       # restore MiniMax routing
pmoves-mini claude-backend backup            # snapshot current settings.json
pmoves-mini claude-backend restore <file>    # restore from a backup
```

Every `set` operation creates `~/.claude/settings.json.bak.<UTC-ISO>` first.

## Per-launch override (no settings.json write)

`claude-pmoves --backend={anthropic|minimax|auto}` overrides the persistent state for a single launch:

- `auto` (default) — detect hijack via `ANTHROPIC_BASE_URL`, restore Anthropic routing if hijacked.
- `anthropic` — explicit Anthropic routing for this launch.
- `minimax` — explicit MiniMax routing for this launch (preserves hijack).

`PMOVES_CLAUDE_BACKEND={anthropic|minimax|auto}` is the env-var equivalent.

## Provenance

- Anthropic template source: `C:\Users\russe\.claude\settings.json.bak.20260910-134430Z` (operator's pre-hijack backup, captured automatically by the Claude Code installer before any plugin/env mutation).
- MiniMax template source: `C:\Users\russe\.claude\settings.json` as of 2026-09-25 (operator's current state, hijacked by Mavis SDK on or around 2026-09-10).
- Slice: `feat/claude-backend-switch` off `feat/pmoves-launcher-generator@4c7316d653`. See `pmoves/docs/AGENTS/claude_backend_switch_LEARNINGS.md` for the full lesson taxonomy.
