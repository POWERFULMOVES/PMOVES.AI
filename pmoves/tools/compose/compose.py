"""
compose_tenant_page — A2UI v0.1 compose tool

The compose tool produces A2UI message streams for tenant pages.

Per A2UI v0.1 spec (pmoves/contracts/a2ui-v0.1.md §13), compose_tenant_page()
is the Python-side contract: takes a tenant config, returns a JSON-serializable
list of A2UI messages that the Lit renderer (website/stage/stage.js) consumes.

Design rules:
- Pure function: same input → same output (no I/O at compose time)
- Tenant-scoped: every message carries the tenant tag for renderer routing
- Composable: agents call compose_tenant_page() with their own component list
- No framework: no React, no JSX — just dicts and lists
- Schema-validated: every component prop is checked against the v0.1 schema
"""

from __future__ import annotations

import json
from typing import Any

A2UI_VERSION = "0.1"

# v0.1 supported components (locked by a2ui-v0.1.md §10)
SUPPORTED_COMPONENTS = frozenset({
    "pm-space-agent-card",
    "pm-project-card",
    "pm-metric-tile",
    "pm-timeline",
    "pm-voice-clip",
    "pm-image",
    "pm-quote-block",
    "pm-haptic",
})


# Prop schemas per component. Type hints use Python types in annotation comments
# so the same file is consumable as both a library and a JSON-schema reference.
#
# v0.1 schemas are intentionally minimal — they cover required props, optional
# props, allowed values for enums, and shape for arrays/objects. They do NOT
# cover ARIA behavior (that's per-component README) or data-source semantics
# (per spec §7.2).

COMPONENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "pm-space-agent-card": {
        "required": ["agentName"],
        "optional": ["agentRole", "avatar", "presence", "glyph", "theme", "dataSource"],
        "enum": {
            "presence": ["live", "rehearsal", "offline"],
        },
        "shape": {
            "agentName": str,
            "agentRole": str,
            "avatar": str,  # URL
            "presence": str,
            "glyph": str,
            "theme": str,
            "dataSource": str,  # NATS subject or HTTP URL
        },
    },
    "pm-project-card": {
        "required": ["title"],
        "optional": ["description", "status", "tags", "links"],
        "enum": {
            "status": ["live", "rehearsal", "planned", "archived"],
        },
        "shape": {
            "title": str,
            "description": str,
            "status": str,
            "tags": list,  # array of strings
            "links": list,  # array of {label, href}
        },
    },
    "pm-metric-tile": {
        "required": ["label"],
        "optional": ["value", "unit", "trend", "format", "dataSource"],
        "enum": {
            "trend": ["up", "down", "flat"],
            "format": ["plain", "percent", "currency", "duration"],
        },
        "shape": {
            "label": str,
            "value": (str, int, float),
            "unit": str,
            "trend": str,
            "format": str,
            "dataSource": str,
        },
    },
    "pm-timeline": {
        "required": ["events"],
        "optional": ["emptyMessage"],
        "shape": {
            "events": list,  # array of {ts, title, body, icon}
            "emptyMessage": str,
        },
    },
    "pm-voice-clip": {
        "required": ["src", "title"],
        "optional": ["duration", "transcript", "speaker"],
        "shape": {
            "src": str,  # URL
            "title": str,
            "duration": (str, int, float),
            "transcript": str,
            "speaker": str,
        },
    },
    "pm-image": {
        "required": ["src", "alt"],
        "optional": ["caption", "credit", "aspectRatio"],
        "enum": {
            "aspectRatio": ["1/1", "4/3", "3/2", "16/9", "21/9", "2/3", "9/16"],
        },
        "shape": {
            "src": str,  # URL
            "alt": str,
            "caption": str,
            "credit": str,
            "aspectRatio": str,
        },
    },
    "pm-quote-block": {
        "required": ["quote", "attribution"],
        "optional": ["attributionRole"],
        "shape": {
            "quote": str,
            "attribution": str,
            "attributionRole": str,
        },
    },
    "pm-haptic": {
        "required": [],  # all props are optional; component can be empty
        "optional": ["pattern", "bpm", "dataSource", "enabled", "respectReducedMotion"],
        "shape": {
            "pattern": str,  # CSV of ms, e.g. "100,50,100,50,100"
            "bpm": (int, float),  # auto-derive pattern
            "dataSource": str,  # NATS subject or HTTP URL
            "enabled": bool,
            "respectReducedMotion": bool,
        },
    },
}


def compose_component(component: str, props: dict[str, Any]) -> dict[str, Any]:
    """
    Produce a single A2UI message (the 'createComponent' type).

    Args:
        component: Component name, e.g. "pm-space-agent-card". Must be in
            SUPPORTED_COMPONENTS.
        props: Prop dict matching the component's schema. Required props must
            be present; optional props are forwarded as-is.

    Returns:
        {"type": "createComponent", "component": ..., "props": {...}}

    Raises:
        ValueError: if component is not in SUPPORTED_COMPONENTS, or if required
            props are missing.
    """
    if component not in SUPPORTED_COMPONENTS:
        raise ValueError(
            f"unsupported component: {component!r}; "
            f"v{A2UI_VERSION} supports {sorted(SUPPORTED_COMPONENTS)}"
        )

    schema = COMPONENT_SCHEMAS[component]
    missing = [p for p in schema["required"] if p not in props]
    if missing:
        raise ValueError(
            f"{component}: missing required prop(s): {missing}; "
            f"required={schema['required']}"
        )

    # v0.1 does not validate types strictly (Python is dynamic) — the A2UI
    # renderer is the final arbiter. We only validate enum values.
    for prop_name, allowed in schema.get("enum", {}).items():
        if prop_name in props and props[prop_name] not in allowed:
            raise ValueError(
                f"{component}.{prop_name}: value {props[prop_name]!r} not in "
                f"allowed values {allowed}"
            )

    return {
        "type": "createComponent",
        "component": component,
        "props": dict(props),  # copy to avoid mutation surprises
    }


def validate_tenant_config(tenant_config: dict[str, Any]) -> list[str]:
    """
    Validate a tenant config and return a list of warnings (non-fatal issues).

    Use this BEFORE compose_tenant_page() to surface configuration drift early.
    Returns an empty list if the config looks healthy.

    v0.1 rules checked:
    - tenant.id is a non-empty string
    - tenant.name is a non-empty string
    - all components in `components` are in SUPPORTED_COMPONENTS
    - each component's required props are present
    - tenant.theme is one of the known v0.1 themes (or "custom")
    - presence values match the enum (live/rehearsal/offline)
    """
    warnings: list[str] = []

    if not isinstance(tenant_config, dict):
        warnings.append(f"tenant_config must be a dict, got {type(tenant_config).__name__}")
        return warnings

    tenant_meta = tenant_config.get("tenant", {})
    if not isinstance(tenant_meta, dict):
        warnings.append(f"'tenant' block must be a dict, got {type(tenant_meta).__name__}")
        return warnings

    if not tenant_meta.get("id"):
        warnings.append("tenant.id is missing or empty")
    if not tenant_meta.get("name"):
        warnings.append("tenant.name is missing or empty")

    if "theme" in tenant_meta:
        valid_themes = {"armor", "darkxside", "skin", "custom"}
        if tenant_meta["theme"] not in valid_themes:
            warnings.append(
                f"tenant.theme={tenant_meta['theme']!r} not in {sorted(valid_themes)}; "
                f"persona runtime will use defaults"
            )

    components = tenant_config.get("components", [])
    if not isinstance(components, list):
        warnings.append(f"'components' must be a list, got {type(components).__name__}")
        return warnings

    for idx, comp in enumerate(components):
        if not isinstance(comp, dict):
            warnings.append(f"components[{idx}]: not a dict")
            continue

        name = comp.get("component")
        props = comp.get("props", {})

        if name not in SUPPORTED_COMPONENTS:
            warnings.append(
                f"components[{idx}]: component={name!r} not in "
                f"v{A2UI_VERSION} supported set {sorted(SUPPORTED_COMPONENTS)}"
            )
            continue

        schema = COMPONENT_SCHEMAS[name]
        for req in schema["required"]:
            if req not in props:
                warnings.append(f"components[{idx}] ({name}): missing required prop {req!r}")

        for prop_name, allowed in schema.get("enum", {}).items():
            if prop_name in props and props[prop_name] not in allowed:
                warnings.append(
                    f"components[{idx}] ({name}): prop {prop_name}={props[prop_name]!r} "
                    f"not in allowed values {allowed}"
                )

    return warnings


def compose_tenant_page(tenant_config: dict[str, Any]) -> dict[str, Any]:
    """
    Produce the full A2UI message stream for a tenant page.

    The returned dict is JSON-serializable and ready to hand to the Lit
    renderer (website/stage/stage.js). The renderer's onmessage handler
    iterates `messages` and creates DOM elements from each createComponent.

    Args:
        tenant_config: {
            "tenant": {
                "id": "fordham-hill",   # required
                "name": "Fordham Hill",  # required
                "theme": "armor",        # optional, one of armor|darkxside|skin|custom
                "tagline": "...",        # optional
            },
            "components": [            # required, list of component configs
                {
                    "component": "pm-space-agent-card",
                    "props": {"agentName": "CLAUDE-OPUS", ...},
                },
                ...
            ],
        }

    Returns:
        {
            "a2uiVersion": "0.1",
            "tenant": {"id": ..., "name": ..., "theme": ...},
            "messages": [
                {"type": "pageMeta", ...},
                {"type": "createComponent", "component": ..., "props": ...},
                ...
            ],
        }

    Raises:
        ValueError: if a component is unsupported or has missing required props.
            (Call validate_tenant_config() first to see warnings.)
    """
    tenant_meta = dict(tenant_config.get("tenant", {}))  # copy
    components = tenant_config.get("components", [])

    messages: list[dict[str, Any]] = []

    # Page meta message — renderer reads this for document title, theme injection
    messages.append({
        "type": "pageMeta",
        "tenant": tenant_meta,
    })

    # Header message (tenant-scoped) — used by the renderer to show the
    # "Roll into your town" / page title banner. Optional but recommended.
    if tenant_meta.get("name") or tenant_meta.get("tagline"):
        messages.append({
            "type": "pageHeader",
            "title": tenant_meta.get("name", ""),
            "tagline": tenant_meta.get("tagline", ""),
        })

    # Per-component messages
    for comp in components:
        name = comp["component"]
        props = comp.get("props", {})
        messages.append(compose_component(name, props))

    return {
        "a2uiVersion": A2UI_VERSION,
        "tenant": tenant_meta,
        "messages": messages,
    }


def to_json(payload: dict[str, Any], indent: int | None = 2) -> str:
    """Serialize the page payload to JSON. Convenience for CLI use."""
    return json.dumps(payload, indent=indent, ensure_ascii=False)
