# pmoves/design/tests/test_generate.py
import json, sys, pathlib
DESIGN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESIGN))

from generate import resolve_theme, load_registry  # noqa: E402  # pyright: ignore[reportMissingImports]


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


def test_emit_css_has_data_theme_selector():
    from generate import emit_css  # pyright: ignore[reportMissingImports]
    reg = load_registry()
    theme = json.load(open(DESIGN / "themes" / "pmoves-armor.json"))
    css = emit_css(theme, resolve_theme(theme, reg))
    assert '[data-theme="pmoves-armor"]' in css
    assert "--pm-accent: #7C3AED;" in css
    # default theme also matches bare :root
    assert ":root:not([data-theme])" in css


def test_emit_ts_exports_theme_map():
    from generate import emit_ts  # pyright: ignore[reportMissingImports]
    reg = load_registry()
    themes = {n: resolve_theme(json.load(open(DESIGN/"themes"/f"{n}.json")), reg)
              for n in ("pmoves-armor", "darkxside-skin")}
    ts = emit_ts(themes)
    assert "export const themes" in ts
    assert '"--pm-signature": "#E11D48"' in ts


def test_unsafe_registry_value_is_rejected():
    # a hostile/typo registry value with a CSS-breaking char must fail loudly,
    # not silently produce broken build/ output (W2).
    reg = {"x": {"color": "#fff; } body{display:none", "accent": "#fff"},
           "darkxside": load_registry()["darkxside"]}
    theme = {"name": "x", "accents": {"primary": "x", "secondary": "darkxside", "signature": "darkxside"}, "overrides": {}}
    try:
        resolve_theme(theme, reg)
        assert False, "expected ValueError on unsafe value"
    except ValueError as e:
        assert "unsafe" in str(e)


def test_missing_field_on_present_agent_raises_clear_error():
    reg = {"x": {"color": "#abcdef"},  # missing 'accent'
           "darkxside": load_registry()["darkxside"]}
    theme = {"name": "x", "accents": {"primary": "x", "secondary": "darkxside", "signature": "darkxside"}, "overrides": {}}
    try:
        resolve_theme(theme, reg)
        assert False, "expected KeyError on missing field"
    except KeyError as e:
        assert "accent" in str(e) and "x" in str(e)
