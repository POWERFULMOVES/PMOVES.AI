"""TAC Tree — Theme-Agent-Character engine for PMOVES.AI service branding.

The TAC tree resolves agent→character mappings from agent-themes.yaml and
generates themed output for multiple targets:

  - CSS custom properties (universal, any web UI)
  - Jellyfin-specific CSS selectors
  - Grafana/dashboard color tokens
  - JSON color manifest for programmatic consumption

Architecture:
  agent-themes.yaml
  ├── theme_packs/ (4 packs × 4-8 characters each)
  ├── agent_theme_map/ (61 agents, primary + secondary character)
  └── TAC engine
      ├── resolve: agent_key → {primary, secondary} character defs
      ├── palette: character → color_palette[3] → CSS vars
      └── render: target-specific CSS/JSON output
"""

import json
import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple

import yaml

_THEMES_PATH = os.environ.get(
    "AGENT_THEMES_PATH",
    str(pathlib.Path(__file__).resolve().parent.parent.parent / "configs" / "agent-themes.yaml"),
)

_cache: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Core: Load & Resolve
# ─────────────────────────────────────────────────────────────────────────────

def _load_themes(path: Optional[str] = None) -> Dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    p = path or _THEMES_PATH
    with open(p, "r", encoding="utf-8") as fh:
        _cache = yaml.safe_load(fh) or {}
    return _cache


def invalidate_cache() -> None:
    global _cache
    _cache = None


def resolve_character(
    theme_pack: str, character_name: str, themes: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Resolve a character definition from theme_packs."""
    data = themes or _load_themes()
    pack = data.get("theme_packs", {}).get(theme_pack)
    if not pack:
        return None
    return pack.get("characters", {}).get(character_name)


def resolve_agent_mapping(
    agent_key: str, themes: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Resolve an agent's primary and secondary character mappings."""
    data = themes or _load_themes()
    entry = data.get("agent_theme_map", {}).get(agent_key)
    if not entry:
        return None
    result: Dict[str, Any] = {"agent": agent_key, "rationale": entry.get("rationale", "")}
    for role in ("primary", "secondary"):
        ref = entry.get(role, "")
        if "/" in ref:
            pack_name, char_name = ref.split("/", 1)
            char_def = resolve_character(pack_name, char_name, data)
            result[role] = {
                "theme_pack": pack_name,
                "character": char_name,
                "definition": char_def,
            }
        else:
            result[role] = None
    return result


def resolve_palette(
    agent_key: str, theme_pack: Optional[str] = None
) -> Dict[str, str]:
    """Resolve flat color palette dict for an agent.

    Returns keys: primary, accent, tertiary, secondary, sec_accent,
    pri_name, sec_name, pri_icon.
    """
    mapping = resolve_agent_mapping(agent_key)
    if not mapping:
        return {}

    palette: Dict[str, str] = {}
    pri = mapping.get("primary")
    if pri and pri.get("definition"):
        char_def = pri["definition"]
        if theme_pack and theme_pack != pri.get("theme_pack"):
            override = resolve_character(theme_pack, pri["character"])
            if override:
                char_def = override
        colors = char_def.get("color_palette", [])
        if len(colors) >= 1:
            palette["primary"] = colors[0]
        if len(colors) >= 2:
            palette["accent"] = colors[1]
        if len(colors) >= 3:
            palette["tertiary"] = colors[2]
        palette["pri_name"] = char_def.get("name", "")
        palette["pri_icon"] = char_def.get("icon", "")
        palette["pri_traits"] = char_def.get("traits", [])

    sec = mapping.get("secondary")
    if sec and sec.get("definition"):
        colors = sec["definition"].get("color_palette", [])
        if len(colors) >= 1:
            palette["sec_primary"] = colors[0]
        if len(colors) >= 2:
            palette["secondary"] = colors[1]
        if len(colors) >= 3:
            palette["sec_tertiary"] = colors[2]
        palette["sec_name"] = sec["definition"].get("name", "")

    palette["rationale"] = mapping.get("rationale", "")
    return palette


# ─────────────────────────────────────────────────────────────────────────────
# Render: CSS Custom Properties (universal)
# ─────────────────────────────────────────────────────────────────────────────

def _palette_vars(char_def: Dict[str, Any], prefix: str) -> List[Tuple[str, str]]:
    """Extract CSS custom property pairs from a character's color_palette."""
    palette = char_def.get("color_palette", [])
    labels = ["primary", "accent", "tertiary"]
    return [
        (f"--pmoves-{prefix}-{labels[i] if i < len(labels) else f'color-{i}'}", color)
        for i, color in enumerate(palette[:3])
    ]


def generate_css_vars(
    agent_key: str = "jellyfin-ai",
    theme_pack: Optional[str] = None,
) -> str:
    """Generate only the :root CSS custom properties block (no selectors).

    This is the universal output — any service can consume these vars.
    """
    themes = _load_themes()
    mapping = resolve_agent_mapping(agent_key, themes)
    if not mapping:
        return f"/* TAC tree: no mapping found for agent '{agent_key}' */\n"

    css_vars: List[Tuple[str, str]] = []

    pri = mapping.get("primary")
    if pri and pri.get("definition"):
        char_def = pri["definition"]
        if theme_pack and theme_pack != pri.get("theme_pack"):
            override = resolve_character(theme_pack, pri["character"], themes)
            if override:
                char_def = override
        css_vars.extend(_palette_vars(char_def, "pri"))
        css_vars.append(("--pmoves-pri-name", f'"{char_def.get("name", "")}"'))
        css_vars.append(("--pmoves-pri-icon", f'"{char_def.get("icon", "")}"'))

    sec = mapping.get("secondary")
    if sec and sec.get("definition"):
        css_vars.extend(_palette_vars(sec["definition"], "sec"))
        css_vars.append(("--pmoves-sec-name", f'"{sec["definition"].get("name", "")}"'))

    # Shorthand aliases
    if pri and pri.get("definition"):
        p = pri["definition"].get("color_palette", [])
        for i, alias in enumerate(["--pmoves-primary", "--pmoves-accent", "--pmoves-tertiary"]):
            if i < len(p):
                css_vars.append((alias, p[i]))
    if sec and sec.get("definition"):
        p = sec["definition"].get("color_palette", [])
        if len(p) >= 2:
            css_vars.append(("--pmoves-secondary", p[1]))

    lines = [
        f"/* TAC Tree — {agent_key} */",
        f"/* Primary: {pri['theme_pack']}/{pri['character']} */" if pri else "",
        f"/* Secondary: {sec['theme_pack']}/{sec['character']} */" if sec else "",
        ":root {",
    ]
    for var_name, var_value in css_vars:
        lines.append(f"  {var_name}: {var_value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# Render: Service-Specific CSS Targets
# ─────────────────────────────────────────────────────────────────────────────

# Each target is a function that returns CSS selector blocks using the
# TAC custom properties. The :root vars block is prepended automatically.

_JELLYFIN_CSS = """
/* ── Jellyfin Header ── */
.skinHeader {
  background: var(--pmoves-primary, #00008B) !important;
}
.skinHeader .headerButton {
  color: var(--pmoves-accent, #FFD700) !important;
}
.skinHeader .headerButton:hover {
  background: rgba(255, 215, 0, 0.15) !important;
}
.headerTabs .emby-tab-button-active {
  border-bottom-color: var(--pmoves-accent, #FFD700) !important;
  color: var(--pmoves-accent, #FFD700) !important;
}

/* ── Jellyfin Sidebar ── */
.mainDrawer {
  background: var(--pmoves-primary, #00008B) !important;
}
.navMenuOption:hover, .navMenuOption-selected {
  background: rgba(255, 215, 0, 0.12) !important;
  color: var(--pmoves-accent, #FFD700) !important;
}

/* ── Jellyfin Buttons ── */
.emby-button-foreground {
  color: var(--pmoves-accent, #FFD700) !important;
}
.button-submit {
  background: var(--pmoves-primary, #00008B) !important;
  color: var(--pmoves-accent, #FFD700) !important;
}
.button-submit:hover {
  background: var(--pmoves-secondary, #800080) !important;
}

/* ── Jellyfin Cards ── */
.card:hover .cardOverlayButton {
  color: var(--pmoves-accent, #FFD700) !important;
}
.cardOverlayButton-br {
  background: var(--pmoves-primary, #00008B) !important;
}

/* ── Jellyfin Progress ── */
.itemProgressBar .itemProgressBarForeground {
  background: var(--pmoves-accent, #FFD700) !important;
}

/* ── Jellyfin Login ── */
.loginPage .padded-left.padded-right {
  background: var(--pmoves-primary, #00008B) !important;
  border-radius: 12px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar-thumb {
  background: var(--pmoves-accent, #FFD700) !important;
  border-radius: 4px;
}
"""

_GRAFANA_CSS = """
/* ── Grafana Overrides (injected via provisioning) ── */
.sidemenu {
  background: var(--pmoves-primary) !important;
}
.navbar {
  background: var(--pmoves-primary) !important;
}
.btn--primary {
  background-color: var(--pmoves-accent) !important;
  border-color: var(--pmoves-accent) !important;
}
"""

_DASHBOARD_CSS = """
/* ── PMOVES Dashboard / Generic Web UI ── */
body {
  --color-primary: var(--pmoves-primary);
  --color-accent: var(--pmoves-accent);
  --color-secondary: var(--pmoves-secondary);
  --color-bg: #0a0a1a;
  --color-card: #111133;
  --color-text: #e0e0e0;
}
.header, nav {
  background: var(--pmoves-primary) !important;
  color: var(--pmoves-accent) !important;
}
a, .link {
  color: var(--pmoves-accent) !important;
}
button.primary, .btn-primary {
  background: var(--pmoves-primary) !important;
  color: var(--pmoves-accent) !important;
  border: 1px solid var(--pmoves-accent) !important;
}
"""

CSS_TARGETS: Dict[str, str] = {
    "jellyfin": _JELLYFIN_CSS,
    "grafana": _GRAFANA_CSS,
    "dashboard": _DASHBOARD_CSS,
}


def generate_tac_css(
    theme_pack: Optional[str] = None,
    agent_key: str = "jellyfin-ai",
    target: str = "jellyfin",
) -> str:
    """Generate a complete CSS stylesheet for a specific service target.

    Combines :root custom properties + target-specific selectors.

    Args:
        theme_pack: Override the agent's default primary pack.
        agent_key: Agent to theme (default: jellyfin-ai).
        target: CSS target — 'jellyfin', 'grafana', 'dashboard', or 'vars-only'.
    """
    vars_css = generate_css_vars(agent_key=agent_key, theme_pack=theme_pack)
    if target == "vars-only":
        return vars_css
    target_css = CSS_TARGETS.get(target, "")
    return vars_css + "\n" + target_css


# ─────────────────────────────────────────────────────────────────────────────
# Render: JSON Color Manifest
# ─────────────────────────────────────────────────────────────────────────────

def generate_color_manifest(
    agent_key: str = "jellyfin-ai",
    theme_pack: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a JSON color manifest for programmatic consumption.

    Useful for non-CSS targets (native apps, API responses, card generation).
    """
    palette = resolve_palette(agent_key, theme_pack)
    mapping = resolve_agent_mapping(agent_key)
    return {
        "agent": agent_key,
        "palette": palette,
        "primary_ref": mapping["primary"]["theme_pack"] + "/" + mapping["primary"]["character"] if mapping and mapping.get("primary") else None,
        "secondary_ref": mapping["secondary"]["theme_pack"] + "/" + mapping["secondary"]["character"] if mapping and mapping.get("secondary") else None,
        "css_targets": list(CSS_TARGETS.keys()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Render: Agent Card (for agent-card-gen FlOO$ pairing)
# ─────────────────────────────────────────────────────────────────────────────

def generate_agent_card_theme(agent_key: str) -> Dict[str, Any]:
    """Generate theming data for agent card generation.

    Used by the agent-card-gen FlOO$ pairing to produce branded agent cards
    with character-appropriate colors, icons, and traits.
    """
    palette = resolve_palette(agent_key)
    if not palette:
        return {"agent": agent_key, "error": "no mapping"}
    return {
        "agent": agent_key,
        "background": palette.get("primary", "#000000"),
        "foreground": palette.get("accent", "#FFFFFF"),
        "accent": palette.get("secondary", "#808080"),
        "icon": palette.get("pri_icon", ""),
        "character_name": palette.get("pri_name", ""),
        "secondary_name": palette.get("sec_name", ""),
        "traits": palette.get("pri_traits", []),
        "rationale": palette.get("rationale", ""),
        "gradient": f"linear-gradient(135deg, {palette.get('primary', '#000')}, {palette.get('secondary', '#333')})",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Query: Tree & Pack Listings
# ─────────────────────────────────────────────────────────────────────────────

def get_tac_tree() -> Dict[str, Any]:
    """Return the full TAC tree structure for dashboard consumption."""
    themes = _load_themes()
    packs_raw = themes.get("theme_packs", {})
    agent_map = themes.get("agent_theme_map", {})

    packs_summary = {}
    for pack_key, pack_data in packs_raw.items():
        chars = {}
        for char_key, char_def in pack_data.get("characters", {}).items():
            chars[char_key] = {
                "name": char_def.get("name", char_key),
                "color_palette": char_def.get("color_palette", []),
                "icon": char_def.get("icon", ""),
                "traits": char_def.get("traits", []),
            }
        packs_summary[pack_key] = {
            "name": pack_data.get("name", pack_key),
            "description": pack_data.get("description", ""),
            "characters": chars,
        }

    agents_summary = {}
    for agent_key, entry in agent_map.items():
        agents_summary[agent_key] = {
            "primary": entry.get("primary", ""),
            "secondary": entry.get("secondary", ""),
            "rationale": entry.get("rationale", ""),
        }

    return {
        "theme_packs": packs_summary,
        "agent_theme_map": agents_summary,
        "pack_names": list(packs_summary.keys()),
        "agent_count": len(agents_summary),
        "css_targets": list(CSS_TARGETS.keys()),
    }


def list_theme_packs() -> List[Dict[str, str]]:
    """Return a list of available theme packs with names and descriptions."""
    themes = _load_themes()
    packs = themes.get("theme_packs", {})
    return [
        {
            "key": k,
            "name": v.get("name", k),
            "description": v.get("description", ""),
            "character_count": len(v.get("characters", {})),
        }
        for k, v in packs.items()
    ]


def list_agents_for_pack(theme_pack: str) -> List[Dict[str, str]]:
    """Return agents whose primary or secondary character is from a given pack."""
    themes = _load_themes()
    agent_map = themes.get("agent_theme_map", {})
    results = []
    for agent_key, entry in agent_map.items():
        pri = entry.get("primary", "")
        sec = entry.get("secondary", "")
        if pri.startswith(f"{theme_pack}/") or sec.startswith(f"{theme_pack}/"):
            results.append({
                "agent": agent_key,
                "primary": pri,
                "secondary": sec,
                "rationale": entry.get("rationale", ""),
            })
    return results
