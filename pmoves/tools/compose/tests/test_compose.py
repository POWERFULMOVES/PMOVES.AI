"""Unit tests for pmoves.tools.compose.

Run with pytest:    pytest pmoves/tools/compose/tests/ -v
Run without pytest: python pmoves/tools/compose/tests/test_compose.py
"""

import json
import pathlib
import sys

try:
    import pytest
except ImportError:
    # Allow running this file as a plain script even when pytest is not
    # installed. The decorators become no-ops and assertions are stdlib.
    class _PytestShim:
        @staticmethod
        def raises(exc_type, match=None):
            class _Ctx:
                def __enter__(self): return self
                def __exit__(self, exc_type_inner, exc, tb):
                    if exc is None:
                        raise AssertionError(f"expected {exc_type_inner.__name__} but no exception raised")
                    if not isinstance(exc, exc_type_inner):
                        return False
                    if match and not _matches(exc, match):
                        raise AssertionError(f"exception {exc_type_inner.__name__}({exc}) did not match pattern {match!r}")
                    return True
            return _Ctx()
    def _matches(exc, pattern):
        import re
        return re.search(pattern, str(exc)) is not None
    pytest = _PytestShim()

# Add the parent tools directory to sys.path so the package imports cleanly
# regardless of how the test runner is invoked.
_TOOLS_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from compose import (  # type: ignore  # noqa: E402
    A2UI_VERSION,
    COMPONENT_SCHEMAS,
    SUPPORTED_COMPONENTS,
    compose_component,
    compose_tenant_page,
    to_json,
    validate_tenant_config,
)


# ---- compose_component ----

def test_compose_component_basic():
    msg = compose_component(
        "pm-space-agent-card",
        {"agentName": "CLAUDE-OPUS", "agentRole": "analytical", "presence": "live"},
    )
    assert msg["type"] == "createComponent"
    assert msg["component"] == "pm-space-agent-card"
    assert msg["props"]["agentName"] == "CLAUDE-OPUS"
    assert msg["props"]["presence"] == "live"


def test_compose_component_unsupported_raises():
    with pytest.raises(ValueError, match="unsupported component"):
        compose_component("pm-not-a-real-thing", {"foo": "bar"})


def test_compose_component_missing_required_raises():
    with pytest.raises(ValueError, match="missing required prop"):
        compose_component("pm-space-agent-card", {"agentRole": "analytical"})


def test_compose_component_invalid_enum_raises():
    with pytest.raises(ValueError, match="not in allowed values"):
        compose_component(
            "pm-space-agent-card",
            {"agentName": "X", "presence": "invalid-presence-state"},
        )


def test_compose_component_props_are_copied():
    """Mutating the returned props dict must not affect the input."""
    original = {"agentName": "X", "agentRole": "test"}
    msg = compose_component("pm-space-agent-card", original)
    msg["props"]["agentName"] = "mutated"
    assert original["agentName"] == "X"


# ---- validate_tenant_config ----

def test_validate_tenant_config_healthy():
    cfg = {
        "tenant": {"id": "fordham-hill", "name": "Fordham Hill", "theme": "armor"},
        "components": [
            {"component": "pm-space-agent-card", "props": {"agentName": "X"}}
        ],
    }
    warnings = validate_tenant_config(cfg)
    assert warnings == []


def test_validate_tenant_config_missing_id_warns():
    cfg = {
        "tenant": {"name": "Fordham Hill"},
        "components": [],
    }
    warnings = validate_tenant_config(cfg)
    assert any("tenant.id" in w for w in warnings)


def test_validate_tenant_config_missing_name_warns():
    cfg = {
        "tenant": {"id": "fordham-hill"},
        "components": [],
    }
    warnings = validate_tenant_config(cfg)
    assert any("tenant.name" in w for w in warnings)


def test_validate_tenant_config_unknown_component_warns():
    cfg = {
        "tenant": {"id": "x", "name": "X"},
        "components": [{"component": "pm-fake-component", "props": {}}],
    }
    warnings = validate_tenant_config(cfg)
    assert any("not in v" in w for w in warnings)


def test_validate_tenant_config_missing_required_warns():
    cfg = {
        "tenant": {"id": "x", "name": "X"},
        "components": [
            {"component": "pm-space-agent-card", "props": {"agentRole": "test"}}
        ],
    }
    warnings = validate_tenant_config(cfg)
    assert any("missing required prop" in w for w in warnings)


def test_validate_tenant_config_unknown_theme_warns():
    cfg = {
        "tenant": {"id": "x", "name": "X", "theme": "vaporwave"},
        "components": [],
    }
    warnings = validate_tenant_config(cfg)
    assert any("tenant.theme" in w for w in warnings)


# ---- compose_tenant_page ----

def test_compose_tenant_page_minimal():
    cfg = {
        "tenant": {"id": "fordham-hill", "name": "Fordham Hill"},
        "components": [
            {"component": "pm-space-agent-card", "props": {"agentName": "X"}}
        ],
    }
    page = compose_tenant_page(cfg)
    assert page["a2uiVersion"] == A2UI_VERSION
    assert page["tenant"]["id"] == "fordham-hill"
    assert page["messages"][0]["type"] == "pageMeta"
    assert page["messages"][1]["type"] == "pageHeader"
    # third message: the component
    assert page["messages"][2]["type"] == "createComponent"
    assert page["messages"][2]["component"] == "pm-space-agent-card"


def test_compose_tenant_page_no_header_when_no_name():
    cfg = {
        "tenant": {"id": "x"},
        "components": [],
    }
    page = compose_tenant_page(cfg)
    # No pageHeader when tenant has no name or tagline
    assert len(page["messages"]) == 1
    assert page["messages"][0]["type"] == "pageMeta"


def test_compose_tenant_page_with_tagline():
    cfg = {
        "tenant": {"id": "x", "name": "X", "tagline": "Hello"},
        "components": [],
    }
    page = compose_tenant_page(cfg)
    assert page["messages"][1]["type"] == "pageHeader"
    assert page["messages"][1]["tagline"] == "Hello"


def test_compose_tenant_page_propagates_component_errors():
    cfg = {
        "tenant": {"id": "x", "name": "X"},
        "components": [
            {"component": "pm-space-agent-card", "props": {}}  # missing agentName
        ],
    }
    with pytest.raises(ValueError, match="missing required prop"):
        compose_tenant_page(cfg)


# ---- Fordham Hill fixture ----

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def test_fordham_hill_fixture_composes_clean():
    cfg = json.loads((FIXTURES / "fordham-hill.json").read_text(encoding="utf-8"))
    warnings = validate_tenant_config(cfg)
    assert warnings == [], f"Fordham Hill fixture has warnings: {warnings}"
    page = compose_tenant_page(cfg)
    assert page["a2uiVersion"] == A2UI_VERSION
    # The fixture exercises ALL 7 v0.1 component types. The exact message
    # count is len(components) + 2 (pageMeta + pageHeader). We assert on
    # component-type presence rather than exact totals so adding more
    # surfaces to the fixture doesn't break this test.
    component_types = [m["component"] for m in page["messages"] if m["type"] == "createComponent"]
    expected_components = {
        "pm-quote-block": 2,
        "pm-image": 1,
        "pm-space-agent-card": 4,
        "pm-project-card": 3,
        "pm-metric-tile": 4,
        "pm-timeline": 1,
        "pm-voice-clip": 1,
    }
    for name, expected_count in expected_components.items():
        actual = component_types.count(name)
        assert actual == expected_count, f"{name}: expected {expected_count}, got {actual}"
    # All 7 v0.1 component types must be represented
    assert set(component_types) == set(expected_components.keys()), \
        f"missing or extra component types: {set(component_types) ^ set(expected_components.keys())}"
    # pageMeta + pageHeader
    assert sum(1 for m in page["messages"] if m["type"] == "pageMeta") == 1
    assert sum(1 for m in page["messages"] if m["type"] == "pageHeader") == 1
    # Total = components + 2
    assert len(page["messages"]) == len(component_types) + 2


# ---- to_json ----

def test_to_json_is_valid_json():
    cfg = {
        "tenant": {"id": "x", "name": "X"},
        "components": [
            {"component": "pm-space-agent-card", "props": {"agentName": "X"}}
        ],
    }
    payload = compose_tenant_page(cfg)
    serialized = to_json(payload)
    parsed = json.loads(serialized)
    assert parsed == payload


# ---- module-level invariants ----

def test_all_supported_components_have_schema():
    for comp in SUPPORTED_COMPONENTS:
        assert comp in COMPONENT_SCHEMAS, f"{comp} missing from COMPONENT_SCHEMAS"


def test_no_duplicate_component_names():
    assert len(SUPPORTED_COMPONENTS) == len(COMPONENT_SCHEMAS)
