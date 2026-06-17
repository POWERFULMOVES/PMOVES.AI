# PMOVES Design Token Layer (DL-1)

A build-time **design token layer** for PMOVES.AI. It reads the canonical persona
registry, merges it with structural base tokens and per-theme overlays, and emits
CSS custom properties + a typed TS token map plus a CSP-clean preview page.

DL-1 is the **token layer** (Model A in the A/B/C plan). It is intentionally
framework-free: stdlib Python + PyYAML for the generator, vanilla JS/CSS/HTML for
the runtime and preview.

## The registry contract (source of truth)

The accent colors come from **`pmoves/config/agent_signatures.yaml`** — the canonical
agent/persona signature registry. DL-1 **reads it read-only**; it never modifies the
registry or its schema.

- Top-level key: `signatures` → `{ <agent-id>: { color, accent, ... } }`.
- A theme references an agent **by id** (e.g. `claude-opus`, `4090-claude`, `darkxside`).
  The generator resolves that id to the agent's `color` (primary/secondary) and
  `accent` (the soft variant).
- If the registry's hex values change, the emitted tokens change on the next
  `make design-tokens` run — values are sourced at build time, never hand-copied.
  (The test fixtures in `tests/test_generate.py` assert the current registry values;
  update them if the registry changes.)

## How to regenerate

```bash
make -C pmoves design-tokens
# or, from this directory:
uv run --no-project --with pyyaml python generate.py
```

This writes `build/tokens.<theme>.css` and `build/tokens.ts`. The `build/` output is
**committed** so consumers (Notebook UI, A2UI, Tailwind, the CF site) need no build
step. A scoped `.gitignore` here re-includes `build/` (the repo root ignores `build/`).

## Themes

| Theme | File | Lead accent | Notes |
|-------|------|-------------|-------|
| `pmoves-armor` (default) | `themes/pmoves-armor.json` | `claude-opus` violet | Cool armor; also matches bare `:root`. |
| `darkxside-skin` | `themes/darkxside-skin.json` | `darkxside` crimson | Warm persona skin. |

## Token naming

All custom properties are namespaced `--pm-*`:

- Accents: `--pm-accent`, `--pm-accent-soft`, `--pm-accent-2`, `--pm-signature`
- Surfaces: `--pm-bg`, `--pm-bg-tint`, `--pm-surface`, `--pm-void`, `--pm-void-elevated`
- Borders: `--pm-border-subtle`, `--pm-border-strong`
- Ink: `--pm-ink`, `--pm-ink-dim`, `--pm-ink-mute`, `--pm-ink-inverse`
- Structure: `--pm-radius`, `--pm-space-{xs,sm,md,lg,xl}`
- Type: `--pm-font-display`, `--pm-font-body`, `--pm-font-mono`

## Runtime + preview

- `theme-provider.js` — dependency-free `setTheme` / `currentTheme` / `toggleTheme`.
  DL-3 will extend it with `setPersona()` resolving via the BoTZ Gateway.
- `preview.html` + `preview.css` + `preview.js` — self-contained, **CSP-clean**
  showcase (no inline style/script bodies, no CDN). Serve and open:
  `uv run python -m http.server 8799` → `http://localhost:8799/preview.html`.

## A/B/C model

- **A (shipped here):** token layer + generator + ThemeProvider + proof surface.
- **B (DL-2):** roll tokens into Notebook (`pmoves/ui`) + A2UI `ProvenancePalette` + CF site.
- **C (DL-3):** persona-adaptive runtime (`theme-provider.setPersona` → gateway).

## Credits — W1 theme lane (4090-claude)

The persona signature registry (`agent_signatures.yaml`) is owned and maintained by
the **W1 theme lane (4090-claude, PRs #1065/#1101)**. DL-1 consumes it with
**additive reads only** and does not touch any W1-owned file
(`pmoves/tools/agent_terminal_theme.py`, `pmoves/tools/botz_cli.py`,
`pmoves/services/botz-gateway/main.py`, or the registry itself).
