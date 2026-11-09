"""Room manifest → OpenRoom shell layout translator.

Reads a room manifest JSON and produces the layout descriptor that the
OpenRoom desktop shell consumes to compose its window/panel grid.

This is the PMOVES-side adapter (layer 4 of the rooms-on-a-stage stack):
manifests → catalog → P7 lifecycle → **room experience (this)**.

The output is a JSON structure consumed by:
  - The OpenRoom fork's `?room=<id>` route handler
  - The /stage/ "Enter" button that navigates to the room desktop
  - P7 session binding (enter/leave lifecycle)

Usage:
    from pmoves.design.room_adapter import translate_manifest
    layout = translate_manifest(manifest_dict)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


POSITION_ORDER = {"top": 0, "left": 1, "center": 2, "right": 3, "bottom": 4}

PANEL_KIND_MAP = {
    "chat": "ChatPanel",
    "controls": "ControlPanel",
    "notebook": "NotebookPanel",
    "logs": "LogPanel",
    "browser": "BrowserPanel",
    "tasks": "TaskPanel",
    "dashboard": "DashboardPanel",
    "custom": "CustomPanel",
}

APP_KIND_MAP = {
    "browser": "BrowserApp",
    "chat": "ChatApp",
    "notebook": "NotebookApp",
    "dashboard": "DashboardApp",
    "graph": "GraphApp",
    "custom": "CustomApp",
}


def translate_panel(panel: dict[str, Any]) -> dict[str, Any]:
    """Translate a manifest panel declaration to an OpenRoom window spec."""
    kind = panel.get("kind", "custom")
    return {
        "id": panel["panel_id"],
        "component": PANEL_KIND_MAP.get(kind, "CustomPanel"),
        "kind": kind,
        "position": panel.get("position", "center"),
        "size_pct": panel.get("size", 50),
        "pinned": panel.get("pinned", False),
        "order": POSITION_ORDER.get(panel.get("position", "center"), 99),
    }


def translate_app(app: dict[str, Any]) -> dict[str, Any]:
    """Translate a manifest app declaration to an OpenRoom app instance."""
    kind = app.get("kind", "custom")
    status = app.get("status", "planned")
    return {
        "id": app["app_id"],
        "component": APP_KIND_MAP.get(kind, "CustomApp"),
        "kind": kind,
        "route": app.get("route"),
        "provider": app.get("provider"),
        "action_namespace": app.get("action_namespace"),
        "capabilities": app.get("capabilities", []),
        "pinned": app.get("pinned", False),
        "status": status,
        "active": status == "active",
    }


def translate_skill_binding(binding: dict[str, Any]) -> dict[str, Any]:
    """Translate a skill binding to an OpenRoom toolbar action."""
    return {
        "id": binding.get("binding_id"),
        "skill_id": binding.get("skill_id"),
        "display_name": binding.get("display_name"),
        "app_id": binding.get("surface", {}).get("app_id"),
        "trigger_phrases": binding.get("activation", {}).get("trigger_phrases", []),
        "enabled": binding.get("enabled", True),
    }


def translate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Translate a full room manifest into an OpenRoom shell layout descriptor.

    Args:
        manifest: A parsed room manifest JSON (from pmoves/config/rooms/*.json)

    Returns:
        A shell layout descriptor with:
          - room identity (room_id, display_name, agent, theme)
          - panels sorted by position (the window grid)
          - apps filtered to active/planned (the operable surfaces)
          - skill bindings (toolbar actions)
          - P7 session binding info
    """
    shell = manifest.get("shell", {})
    theme = shell.get("theme", {})
    layout = shell.get("layout", {})

    panels = sorted(
        [translate_panel(p) for p in layout.get("panels", [])],
        key=lambda p: p["order"],
    )

    apps = [translate_app(a) for a in manifest.get("apps", [])]
    active_apps = [a for a in apps if a["active"]]
    planned_apps = [a for a in apps if not a["active"]]

    skills = [
        translate_skill_binding(b)
        for b in manifest.get("skill_bindings", [])
        if b.get("enabled", True)
    ]

    persona = manifest.get("persona", {})

    return {
        "room_id": manifest.get("room_id"),
        "display_name": manifest.get("display_name"),
        "stage": manifest.get("stage", "rehearsal"),
        "room_type": manifest.get("room_type", "operator"),
        "agent_id": manifest.get("agent_id"),
        "alter": manifest.get("alter"),
        "theme": {
            "id": theme.get("theme_id"),
            "accent": theme.get("accent_color", "#7C3AED"),
            "skin": theme.get("skin"),
            "icon": theme.get("icon", "cube"),
        },
        "persona": {
            "signature_ref": persona.get("signature_ref"),
            "voice": persona.get("voice"),
            "glyph": persona.get("glyph"),
            "resonance": persona.get("resonance", []),
        },
        "layout": {
            "default_route": layout.get("default_route", "/"),
            "panels": panels,
        },
        "apps": {
            "active": active_apps,
            "planned": planned_apps,
        },
        "toolbar_actions": skills,
        "p7": {
            "room_id": manifest.get("room_id"),
            "stage": manifest.get("stage", "rehearsal"),
            "chit_card_id": manifest.get("meta", {}).get("chit", {}).get("card_id"),
        },
        "combiner": manifest.get("combiner_config"),
    }


def load_and_translate(room_path: str | Path) -> dict[str, Any]:
    """Load a room manifest file and translate it."""
    path = Path(room_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return translate_manifest(manifest)
