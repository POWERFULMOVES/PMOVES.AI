"""
pmoves.tools.compose
====================

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

Public surface:
- compose_tenant_page(tenant_config) -> dict (the page payload)
- compose_component(component_name, props) -> dict (a single A2UI message)
- validate_tenant_config(tenant_config) -> list[str] (warnings, not errors)
- COMPONENT_SCHEMAS (dict) — the v0.1 prop schema per component

See: pmoves/contracts/a2ui-v0.1.md, pmoves/web-components/*/README.md
"""

from .compose import (
    compose_tenant_page,
    compose_component,
    validate_tenant_config,
    to_json,
    COMPONENT_SCHEMAS,
    A2UI_VERSION,
    SUPPORTED_COMPONENTS,
)

__all__ = [
    "compose_tenant_page",
    "compose_component",
    "validate_tenant_config",
    "to_json",
    "COMPONENT_SCHEMAS",
    "A2UI_VERSION",
    "SUPPORTED_COMPONENTS",
]
