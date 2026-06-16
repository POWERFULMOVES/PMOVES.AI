# DL-1 Design Token Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `pmoves/design/` — a build-time token layer that reads the canonical persona registry (`pmoves/config/agent_signatures.yaml`) and emits CSS variables + a TS token map, with a self-contained CSP-clean preview page proving both the PMOVES armor and DARKXSIDE skin themes.

**Architecture:** A small `uv`-run Python generator merges three JSON inputs — base neutrals (`tokens.base.json`), per-theme overlays (`themes/*.json`), and the live registry accents — into `build/tokens.<theme>.css` (`:root`/`[data-theme]` custom properties) and `build/tokens.ts` (typed map for A2UI/Tailwind). A tiny dependency-free `theme-provider.js` swaps `data-theme` at runtime. A static `preview.html` renders swatches + motif kit for both themes, importing only generated assets (no CDN, no inline — CSP-clean). DL-1 reads the registry but never modifies it or any 4090-owned file.

**Tech Stack:** Python 3.12 (stdlib + PyYAML via `uv run --with pyyaml`), vanilla JS/CSS/HTML. No framework, no build bundler.

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `pmoves/design/tokens.base.json` | Brand neutrals + structural tokens (void/ink/surface/border ramps, spacing, radius, easing, font stacks). Theme-independent. |
| `pmoves/design/themes/pmoves-armor.json` | Default cool theme: which registry agents supply accent/accent-2/signature; radius/font overrides (none). |
| `pmoves/design/themes/darkxside-skin.json` | Warm persona theme: DARKXSIDE `✦` crimson leads; warm surface tint. |
| `pmoves/design/generate.py` | Generator: merge base + theme + registry → `build/tokens.<theme>.css` + `build/tokens.ts`. |
| `pmoves/design/tests/test_generate.py` | TDD: assert merge logic, CSS var output, registry-sourced accents, fail-safe on missing registry. |
| `pmoves/design/build/` | Generated output (`tokens.pmoves-armor.css`, `tokens.darkxside-skin.css`, `tokens.ts`). Committed so consumers need no build step. |
| `pmoves/design/theme-provider.js` | ~30-line dependency-free runtime: set `data-theme`, optional persona→theme resolve. |
| `pmoves/design/preview.html` | Self-contained proof/showcase: swatches + CTA/ghost + motif kit, both themes, theme toggle. CSP-clean. |
| `pmoves/design/README.md` | Documents the layer, the registry contract, and credits the 4090 W1 lane. |

---

## Token contracts (locked)

**`tokens.base.json`** — structural, theme-independent:
```json
{
  "color": {
    "void": "#050508", "void-elevated": "#0a0a0f", "surface": "#12121a",
    "border-subtle": "rgba(255,255,255,0.08)", "border-strong": "rgba(255,255,255,0.15)",
    "ink": "#f8f8f8", "ink-dim": "#a0a0a8", "ink-mute": "#606068", "ink-inverse": "#050508"
  },
  "radius": { "sm": "4px", "md": "8px", "lg": "14px" },
  "space": { "xs": "4px", "sm": "8px", "md": "16px", "lg": "24px", "xl": "40px" },
  "ease": { "out-expo": "cubic-bezier(0.16,1,0.3,1)", "out-back": "cubic-bezier(0.34,1.56,0.64,1)" },
  "font": {
    "display": "Orbitron, 'Exo 2', system-ui, sans-serif",
    "body": "'Exo 2', system-ui, sans-serif",
    "mono": "'JetBrains Mono', ui-monospace, monospace"
  }
}
```

**`themes/pmoves-armor.json`** — references registry agent ids for accents:
```json
{
  "name": "pmoves-armor",
  "label": "PMOVES Armor",
  "register": "human",
  "accents": { "primary": "claude-opus", "secondary": "4090-claude", "signature": "darkxside" },
  "overrides": { "color": { "bg": "#050508", "bg-tint": "#0a0a12" } }
}
```

**`themes/darkxside-skin.json`** — warm persona skin:
```json
{
  "name": "darkxside-skin",
  "label": "DARKXSIDE Skin",
  "register": "human",
  "accents": { "primary": "darkxside", "secondary": "claude-opus", "signature": "darkxside" },
  "overrides": { "color": { "bg": "#0a0608", "bg-tint": "#140a0e" } }
}
```

A theme's `accents.<role>` is an **agent id**; the generator resolves it to that agent's `color` (primary/secondary) and `accent` (the soft variant) from `agent_signatures.yaml`. `signature` resolves to the agent's `color` exposed as `--pm-signature`.

**Generated CSS shape** (`build/tokens.pmoves-armor.css`):
```css
:root[data-theme="pmoves-armor"], :root:not([data-theme]) {
  --pm-bg: #050508;
  --pm-bg-tint: #0a0a12;
  --pm-surface: #12121a;
  --pm-border-subtle: rgba(255,255,255,0.08);
  --pm-ink: #f8f8f8;
  --pm-ink-dim: #a0a0a8;
  --pm-accent: #7C3AED;        /* claude-opus.color */
  --pm-accent-soft: #A78BFA;   /* claude-opus.accent */
  --pm-accent-2: #0D9488;      /* 4090-claude.color */
  --pm-signature: #E11D48;     /* darkxside.color */
  --pm-radius: 14px;
  --pm-font-display: Orbitron, 'Exo 2', system-ui, sans-serif;
  /* …remaining base tokens… */
}
```

---

## Task 1: Scaffold `pmoves/design/` + base tokens

**Files:**
- Create: `pmoves/design/tokens.base.json`
- Create: `pmoves/design/themes/pmoves-armor.json`
- Create: `pmoves/design/themes/darkxside-skin.json`

- [ ] **Step 1:** Write the three JSON files exactly as in "Token contracts" above.
- [ ] **Step 2:** Validate JSON parses.

Run: `uv run python -c "import json,glob; [json.load(open(f)) for f in glob.glob('pmoves/design/**/*.json',recursive=True)]; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**
```bash
git add pmoves/design/tokens.base.json pmoves/design/themes/
git commit -m "feat(design): DL-1 base + theme token definitions"
```

## Task 2: Generator — registry resolution (TDD)

**Files:**
- Create: `pmoves/design/generate.py`
- Test: `pmoves/design/tests/test_generate.py`

- [ ] **Step 1: Write the failing test**
```python
# pmoves/design/tests/test_generate.py
import json, subprocess, sys, pathlib
DESIGN = pathlib.Path(__file__).resolve().parents[1]

from generate import resolve_theme, load_registry  # noqa: E402

def test_resolve_pmoves_armor_accents_from_registry():
    reg = load_registry()
    theme = json.load(open(DESIGN / "themes" / "pmoves-armor.json"))
    vars_ = resolve_theme(theme, reg)
    assert vars_["--pm-accent"] == "#7C3AED"        # claude-opus.color
    assert vars_["--pm-accent-soft"] == "#A78BFA"   # claude-opus.accent
    assert vars_["--pm-accent-2"] == "#0D9488"      # 4090-claude.color
    assert vars_["--pm-signature"] == "#E11D48"     # darkxside.color

def test_resolve_darkxside_skin_signature_leads():
    reg = load_registry()
    theme = json.load(open(DESIGN / "themes" / "darkxside-skin.json"))
    vars_ = resolve_theme(theme, reg)
    assert vars_["--pm-accent"] == "#E11D48"         # darkxside.color
    assert vars_["--pm-bg"] == "#0a0608"             # override

def test_missing_agent_raises_clear_error():
    reg = load_registry()
    bad = {"name": "x", "accents": {"primary": "no-such-agent", "secondary": "darkxside", "signature": "darkxside"}, "overrides": {}}
    try:
        resolve_theme(bad, reg)
        assert False, "expected KeyError"
    except KeyError as e:
        assert "no-such-agent" in str(e)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pmoves/design && uv run --with pyyaml python -m pytest tests/test_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generate'`

- [ ] **Step 3: Write minimal implementation**
```python
# pmoves/design/generate.py
"""DL-1 design token generator. Reads pmoves/config/agent_signatures.yaml
(registry owned by the W1 theme lane — 4090-claude PRs #1065/#1101; do NOT
modify the registry schema here) + base/theme JSON, emits CSS + TS tokens."""
from __future__ import annotations
import json, pathlib
DESIGN = pathlib.Path(__file__).resolve().parent
REPO = DESIGN.parents[1]
REGISTRY = REPO / "pmoves" / "config" / "agent_signatures.yaml"

def load_registry() -> dict:
    import yaml
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    return data.get("signatures", {})

def _agent(reg: dict, agent_id: str) -> dict:
    if agent_id not in reg:
        raise KeyError(f"theme references unknown agent id: {agent_id!r}")
    return reg[agent_id]

def resolve_theme(theme: dict, reg: dict) -> dict:
    base = json.loads((DESIGN / "tokens.base.json").read_text(encoding="utf-8"))
    v: dict[str, str] = {}
    # structural base
    for k, val in base["color"].items():
        v[f"--pm-{k}"] = val
    v["--pm-radius"] = base["radius"]["lg"]
    for k, val in base["space"].items():
        v[f"--pm-space-{k}"] = val
    v["--pm-font-display"] = base["font"]["display"]
    v["--pm-font-body"] = base["font"]["body"]
    v["--pm-font-mono"] = base["font"]["mono"]
    # registry-sourced accents
    acc = theme["accents"]
    primary = _agent(reg, acc["primary"]); secondary = _agent(reg, acc["secondary"]); sig = _agent(reg, acc["signature"])
    v["--pm-accent"] = primary["color"]
    v["--pm-accent-soft"] = primary["accent"]
    v["--pm-accent-2"] = secondary["color"]
    v["--pm-signature"] = sig["color"]
    # theme overrides last
    for k, val in theme.get("overrides", {}).get("color", {}).items():
        v[f"--pm-{k}"] = val
    return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pmoves/design && uv run --with pyyaml python -m pytest tests/test_generate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**
```bash
git add pmoves/design/generate.py pmoves/design/tests/test_generate.py
git commit -m "feat(design): DL-1 token generator — registry accent resolution (TDD)"
```

## Task 3: Generator — emit CSS + TS (TDD)

**Files:**
- Modify: `pmoves/design/generate.py`
- Test: `pmoves/design/tests/test_generate.py`

- [ ] **Step 1: Add failing tests**
```python
def test_emit_css_has_data_theme_selector(tmp_path):
    from generate import emit_css
    reg = load_registry()
    theme = json.load(open(DESIGN / "themes" / "pmoves-armor.json"))
    css = emit_css(theme, resolve_theme(theme, reg))
    assert '[data-theme="pmoves-armor"]' in css
    assert "--pm-accent: #7C3AED;" in css
    # default theme also matches bare :root
    assert ":root:not([data-theme])" in css

def test_emit_ts_exports_theme_map():
    from generate import emit_ts
    reg = load_registry()
    themes = {n: resolve_theme(json.load(open(DESIGN/"themes"/f"{n}.json")), reg)
              for n in ("pmoves-armor", "darkxside-skin")}
    ts = emit_ts(themes)
    assert "export const themes" in ts
    assert '"--pm-signature": "#E11D48"' in ts
```

- [ ] **Step 2: Run to verify fail**

Run: `cd pmoves/design && uv run --with pyyaml python -m pytest tests/test_generate.py -v`
Expected: FAIL — `ImportError: cannot import name 'emit_css'`

- [ ] **Step 3: Implement emit + main**
```python
DEFAULT_THEME = "pmoves-armor"

def emit_css(theme: dict, vars_: dict) -> str:
    name = theme["name"]
    sel = f'[data-theme="{name}"]'
    if name == DEFAULT_THEME:
        sel += ", :root:not([data-theme])"
    lines = [f"/* generated by pmoves/design/generate.py — do not edit */",
             f":root{sel} {{"]
    for k in sorted(vars_):
        lines.append(f"  {k}: {vars_[k]};")
    lines.append("}")
    return "\n".join(lines) + "\n"

def emit_ts(themes: dict) -> str:
    body = json.dumps(themes, indent=2, sort_keys=True)
    return ("// generated by pmoves/design/generate.py — do not edit\n"
            f"export const themes = {body} as const;\n"
            "export type ThemeName = keyof typeof themes;\n")

def main() -> int:
    reg = load_registry()
    out = DESIGN / "build"; out.mkdir(exist_ok=True)
    resolved = {}
    for tf in sorted((DESIGN / "themes").glob("*.json")):
        theme = json.loads(tf.read_text(encoding="utf-8"))
        vars_ = resolve_theme(theme, reg)
        resolved[theme["name"]] = vars_
        (out / f"tokens.{theme['name']}.css").write_text(emit_css(theme, vars_), encoding="utf-8")
    (out / "tokens.ts").write_text(emit_ts(resolved), encoding="utf-8")
    print(f"generated {len(resolved)} themes -> {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests + generate**

Run: `cd pmoves/design && uv run --with pyyaml python -m pytest tests/test_generate.py -v && uv run --with pyyaml python generate.py`
Expected: PASS (5 passed); `generated 2 themes -> .../build`

- [ ] **Step 5: Commit** (include generated build so consumers need no build step)
```bash
git add pmoves/design/generate.py pmoves/design/tests/test_generate.py pmoves/design/build/
git commit -m "feat(design): DL-1 emit tokens.css + tokens.ts; generate armor + skin"
```

## Task 4: ThemeProvider + preview page

**Files:**
- Create: `pmoves/design/theme-provider.js`
- Create: `pmoves/design/preview.html`

- [ ] **Step 1: Write `theme-provider.js`**
```javascript
// pmoves/design/theme-provider.js — dependency-free theme switch.
// DL-3 will extend setPersona() to resolve via BoTZ Gateway /v1/agent/theme/{id}.
export function setTheme(name) { document.documentElement.setAttribute("data-theme", name); }
export function currentTheme() { return document.documentElement.getAttribute("data-theme") || "pmoves-armor"; }
export function toggleTheme(a = "pmoves-armor", b = "darkxside-skin") {
  setTheme(currentTheme() === a ? b : a);
}
```

- [ ] **Step 2: Write `preview.html`** (CSP-clean: links generated CSS, imports local JS module, no inline style/script bodies, no CDN). Renders both themes' swatches, a CTA + ghost button, and the motif kit (shard dot, hex cell, `✦`). Loads both `tokens.*.css` files; the active `[data-theme]` wins.
```html
<!DOCTYPE html>
<html lang="en" data-theme="pmoves-armor">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>PMOVES Design Tokens — Preview</title>
  <link rel="stylesheet" href="./build/tokens.pmoves-armor.css">
  <link rel="stylesheet" href="./build/tokens.darkxside-skin.css">
  <link rel="stylesheet" href="./preview.css">
</head>
<body>
  <header><h1>PMOVES Design Tokens</h1>
    <button id="toggle" class="cta">Toggle armor / skin</button></header>
  <section class="swatches">
    <span class="sw" data-var="--pm-accent">accent</span>
    <span class="sw" data-var="--pm-accent-2">accent-2</span>
    <span class="sw" data-var="--pm-signature">✦ signature</span>
    <span class="sw" data-var="--pm-surface">surface</span>
  </section>
  <section class="motifs">
    <span class="shard"></span><span class="hex"></span><span class="star">✦</span>
  </section>
  <script type="module" src="./preview.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `preview.css` + `preview.js`** (separate files to keep HTML inline-free for CSP):
```css
/* pmoves/design/preview.css */
body { background: var(--pm-bg); color: var(--pm-ink); font-family: var(--pm-font-body); margin: 0; padding: var(--pm-space-xl); }
h1 { font-family: var(--pm-font-display); }
.cta { background: linear-gradient(135deg, var(--pm-accent), var(--pm-accent-2)); color: #fff; border: 0; padding: 10px 16px; border-radius: var(--pm-radius); cursor: pointer; }
.swatches { display: flex; gap: 12px; margin: 24px 0; }
.sw { width: 120px; height: 64px; border-radius: var(--pm-radius); display: flex; align-items: end; padding: 6px; font-size: 11px; color: #fff; border: 1px solid var(--pm-border-subtle); }
.sw[data-var="--pm-accent"]{background:var(--pm-accent)} .sw[data-var="--pm-accent-2"]{background:var(--pm-accent-2)}
.sw[data-var="--pm-signature"]{background:var(--pm-signature)} .sw[data-var="--pm-surface"]{background:var(--pm-surface)}
.motifs{display:flex;gap:20px;align-items:center}
.shard{width:0;height:0;border-left:14px solid transparent;border-right:14px solid transparent;border-bottom:24px solid var(--pm-accent-2)}
.hex{width:26px;height:23px;background:var(--pm-surface);border:1px solid var(--pm-accent);clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)}
.star{font-size:28px;color:var(--pm-signature)}
```
```javascript
// pmoves/design/preview.js
import { toggleTheme } from "./theme-provider.js";
document.getElementById("toggle").addEventListener("click", () => toggleTheme());
```

- [ ] **Step 4: Manual verify**

Run: `cd pmoves/design && uv run python -m http.server 8799` then open `http://localhost:8799/preview.html`, click toggle.
Expected: armor (violet/teal accents, crimson `✦`) ↔ skin (crimson-led, warm bg). Confirm via Playwright/chrome-devtools screenshot at the end.

- [ ] **Step 5: Commit**
```bash
git add pmoves/design/theme-provider.js pmoves/design/preview.html pmoves/design/preview.css pmoves/design/preview.js
git commit -m "feat(design): DL-1 ThemeProvider + CSP-clean token preview page"
```

## Task 5: README + Make target

**Files:**
- Create: `pmoves/design/README.md`
- Modify: `pmoves/Makefile` (add `design-tokens` target)

- [ ] **Step 1: Write `README.md`** documenting: purpose, the registry contract (`agent_signatures.yaml` is the source of truth, owned by the W1 theme lane / 4090-claude PRs #1065/#1101 — additive reads only), how to regenerate, theme list, token naming, and the A/B/C model (A shipped here). Include the 4090 credit block.
- [ ] **Step 2: Add Make target**
```makefile
design-tokens: ## Regenerate pmoves/design token CSS + TS from agent_signatures.yaml
	cd design && uv run --with pyyaml python generate.py
```
- [ ] **Step 3: Verify**

Run: `make -C pmoves design-tokens`
Expected: `generated 2 themes -> .../build`

- [ ] **Step 4: Commit**
```bash
git add pmoves/design/README.md pmoves/Makefile
git commit -m "docs(design): DL-1 README + make design-tokens target (credits W1 lane)"
```

---

## Self-review notes

- **Spec coverage:** DL-1 (token layer + generator + ThemeProvider, proof surface) ✓; uses registry per D1 ✓; Model A default + skin per D2 ✓; fonts as tokens per D2c ✓; motif kit in preview per D3 ✓. CHIT tour re-skin is **deferred** (tour is on a held branch) → teed up as a follow-on, not in DL-1. DL-2/3/4 out of scope by design.
- **No 4090-owned files touched:** only creates `pmoves/design/*` + appends one Make target; reads `agent_signatures.yaml` read-only. ✓
- **Type consistency:** `resolve_theme`/`emit_css`/`emit_ts`/`load_registry`/`main` names consistent across tasks; CSS var names (`--pm-accent`, `--pm-accent-soft`, `--pm-accent-2`, `--pm-signature`) consistent between contract, generator, and preview. ✓
- **Hex provenance:** all accent hexes resolve from the registry at build time (not hand-copied); `#7C3AED`/`#A78BFA`/`#0D9488`/`#E11D48` shown in tests are assertions against current registry values — if the registry changes, update the test fixtures.

## Teed-up follow-on lanes (not part of this PR)

1. **DL-1b — CHIT tour re-skin:** on the tour branch, import `tokens.pmoves-armor.css`, drop teal/amber, apply motif kit. Separate PR after DL-1 merges.
2. **DL-2 — roll tokens to Notebook (`pmoves/ui`) + A2UI `ProvenancePalette` + CF site token-swap.**
3. **DL-3 — persona-adaptive runtime (`theme-provider.setPersona` → gateway) + Showtime "live" skin.**
4. **DL-4 — CF site rebuilt from A2UI components (demonstrative) + optional light theme.**
