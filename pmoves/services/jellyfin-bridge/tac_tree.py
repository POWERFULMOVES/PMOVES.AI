"""TAC Tree — Theme-Agent-Character CSS generator for Jellyfin PMOVES.AI branding.

Reads agent-themes.yaml, resolves agent→character mappings, and produces CSS
custom properties + Jellyfin-specific selectors for dynamic theming.
"""

import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple

import yaml

_THEMES_PATH = os.environ.get(
    "AGENT_THEMES_PATH",
    str(pathlib.Path(__file__).resolve().parent.parent.parent / "configs" / "agent-themes.yaml"),
)

_cache: Optional[Dict[str, Any]] = None


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
    packs = data.get("theme_packs", {})
    pack = packs.get(theme_pack)
    if not pack:
        return None
    chars = pack.get("characters", {})
    return chars.get(character_name)


def resolve_agent_mapping(
    agent_key: str, themes: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Resolve an agent's primary and secondary character mappings."""
    data = themes or _load_themes()
    agent_map = data.get("agent_theme_map", {})
    entry = agent_map.get(agent_key)
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


def _palette_vars(char_def: Dict[str, Any], prefix: str) -> List[Tuple[str, str]]:
    """Extract CSS custom property pairs from a character's color_palette."""
    palette = char_def.get("color_palette", [])
    labels = ["primary", "accent", "tertiary"]
    pairs = []
    for i, color in enumerate(palette[:3]):
        label = labels[i] if i < len(labels) else f"color-{i}"
        pairs.append((f"--pmoves-{prefix}-{label}", color))
    return pairs


def generate_tac_css(
    theme_pack: Optional[str] = None,
    agent_key: str = "jellyfin-ai",
) -> str:
    """Generate a complete CSS stylesheet for Jellyfin using TAC tree mappings.

    If *theme_pack* is provided, override the agent's default primary pack.
    """
    themes = _load_themes()
    mapping = resolve_agent_mapping(agent_key, themes)
    if not mapping:
        return f"/* TAC tree: no mapping found for agent '{agent_key}' */\n"

    css_vars: List[Tuple[str, str]] = []

    # Primary character
    pri = mapping.get("primary")
    if pri and pri.get("definition"):
        char_def = pri["definition"]
        # If caller overrides theme_pack, re-resolve primary character from that pack
        if theme_pack and theme_pack != pri.get("theme_pack"):
            override_char = resolve_character(theme_pack, pri["character"], themes)
            if override_char:
                char_def = override_char
        css_vars.extend(_palette_vars(char_def, "pri"))
        css_vars.append(("--pmoves-pri-name", f'"{char_def.get("name", "")}"'))
        css_vars.append(("--pmoves-pri-icon", f'"{char_def.get("icon", "")}"'))

    # Secondary character
    sec = mapping.get("secondary")
    if sec and sec.get("definition"):
        css_vars.extend(_palette_vars(sec["definition"], "sec"))
        css_vars.append(("--pmoves-sec-name", f'"{sec["definition"].get("name", "")}"'))

    # Build shorthand aliases
    if pri and pri.get("definition"):
        palette = pri["definition"].get("color_palette", [])
        if len(palette) >= 1:
            css_vars.append(("--pmoves-primary", palette[0]))
        if len(palette) >= 2:
            css_vars.append(("--pmoves-accent", palette[1]))
        if len(palette) >= 3:
            css_vars.append(("--pmoves-tertiary", palette[2]))
    if sec and sec.get("definition"):
        palette = sec["definition"].get("color_palette", [])
        if len(palette) >= 2:
            css_vars.append(("--pmoves-secondary", palette[1]))

    # Render CSS
    lines = [
        f"/* TAC Tree — {agent_key} */",
        f"/* Primary: {pri['theme_pack']}/{pri['character']} */" if pri else "",
        f"/* Secondary: {sec['theme_pack']}/{sec['character']} */" if sec else "",
        ":root {",
    ]
    for var_name, var_value in css_vars:
        lines.append(f"  {var_name}: {var_value};")
    lines.append("}")
    lines.append("")

    # Jellyfin-specific selectors
    lines.extend([
        "/* ── Jellyfin Header ── */",
        ".skinHeader {",
        "  background: var(--pmoves-primary, #00008B) !important;",
        "}",
        ".skinHeader .headerButton {",
        "  color: var(--pmoves-accent, #FFD700) !important;",
        "}",
        ".skinHeader .headerButton:hover {",
        "  background: rgba(255, 215, 0, 0.15) !important;",
        "}",
        ".headerTabs .emby-tab-button-active {",
        "  border-bottom-color: var(--pmoves-accent, #FFD700) !important;",
        "  color: var(--pmoves-accent, #FFD700) !important;",
        "}",
        "",
        "/* ── Jellyfin Sidebar ── */",
        ".mainDrawer {",
        "  background: var(--pmoves-primary, #00008B) !important;",
        "}",
        ".navMenuOption:hover, .navMenuOption-selected {",
        "  background: rgba(255, 215, 0, 0.12) !important;",
        "  color: var(--pmoves-accent, #FFD700) !important;",
        "}",
        "",
        "/* ── Jellyfin Buttons ── */",
        ".emby-button-foreground {",
        "  color: var(--pmoves-accent, #FFD700) !important;",
        "}",
        ".button-submit {",
        "  background: var(--pmoves-primary, #00008B) !important;",
        "  color: var(--pmoves-accent, #FFD700) !important;",
        "}",
        ".button-submit:hover {",
        "  background: var(--pmoves-secondary, #800080) !important;",
        "}",
        "",
        "/* ── Jellyfin Cards ── */",
        ".card:hover .cardOverlayButton {",
        "  color: var(--pmoves-accent, #FFD700) !important;",
        "}",
        ".cardOverlayButton-br {",
        "  background: var(--pmoves-primary, #00008B) !important;",
        "}",
        "",
        "/* ── Jellyfin Progress ── */",
        ".itemProgressBar .itemProgressBarForeground {",
        "  background: var(--pmoves-accent, #FFD700) !important;",
        "}",
        "",
        "/* ── Jellyfin Login ── */",
        ".loginPage .padded-left.padded-right {",
        "  background: var(--pmoves-primary, #00008B) !important;",
        "  border-radius: 12px;",
        "}",
        "",
        "/* ── Scrollbar ── */",
        "::-webkit-scrollbar-thumb {",
        "  background: var(--pmoves-accent, #FFD700) !important;",
        "  border-radius: 4px;",
        "}",
    ])

    return "\n".join(lines) + "\n"


def get_tac_tree() -> Dict[str, Any]:
    """Return the full TAC tree structure for dashboard consumption."""
    themes = _load_themes()
    packs_raw = themes.get("theme_packs", {})
    agent_map = themes.get("agent_theme_map", {})

    # Summarise packs
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

    # Summarise agent mappings
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
