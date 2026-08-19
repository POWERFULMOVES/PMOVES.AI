"""
Regression test: the canonical example.cgp.yaml must validate
against the v1.schema.json.

Context: PR #2612 (mcpcli-wireup) added a 'minimax' entry to
example.cgp.yaml's services block. The v1.schema.json had
`services.additionalProperties: false`, so the canonical example
was invalid — every consumer fork that loaded the bootstrap got a
jsonschema validation error. A codex review on #2612 caught this
as a P1: 'extend the schema and add a validation test for the
example'.

The schema fix landed in commit 346763f55 (add 'minimax' to
services.properties). This test is the second half of the
codex recommendation: a test that pins the example to the
schema, so the two never drift apart again without being
caught at PR time.

Without this test, a future PR could:
  - Add a new service key to example.cgp.yaml without updating
    v1.schema.json's services.properties whitelist
  - Or update v1.schema.json with a typo / wrong structure
And neither change would fail any test in the existing suite
because the example is loaded as a YAML dict, not validated
against the schema at any point in the runtime path. The
validation happens at schema-parse time in the consumer
forks, far from the source of the drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


# Repo root is two parents up from pmoves/tests/.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT
    / "pmoves"
    / "contracts"
    / "schemas"
    / "pmoves-bootstrap"
    / "v1.schema.json"
)
EXAMPLE_PATH = (
    REPO_ROOT
    / "pmoves"
    / "contracts"
    / "schemas"
    / "pmoves-bootstrap"
    / "example.cgp.yaml"
)


@pytest.fixture(scope="module")
def schema() -> dict:
    """The v1 schema as a parsed dict."""
    if not SCHEMA_PATH.exists():
        pytest.skip(f"schema not present at {SCHEMA_PATH}")
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def example() -> dict:
    """The canonical example.cgp.yaml as a parsed dict."""
    if not EXAMPLE_PATH.exists():
        pytest.skip(f"example not present at {EXAMPLE_PATH}")
    with EXAMPLE_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# Schema-level assertions
# ============================================================================


def test_schema_spec_is_pmoves_bootstrap_v1(schema: dict) -> None:
    """The schema declares the spec profile as 'pmoves.bootstrap/v1'.

    The 'spec' field is inside properties.spec.const (the JSON
    Schema convention for a fixed string enum). This test pins
    that const so a future PR that accidentally changes the
    profile name (e.g., to 'pmoves.bootstrap/v2') is caught
    here, with a clear 'you also need to update the example +
    the consumer forks' message.
    """
    spec_const = schema.get("properties", {}).get("spec", {}).get("const")
    assert spec_const == "pmoves.bootstrap/v1", (
        f"schema.properties.spec.const must be 'pmoves.bootstrap/v1'; "
        f"got {spec_const!r}"
    )


def test_schema_has_services_block_with_closed_property_set(schema: dict) -> None:
    """The services block is an object with additionalProperties: false.

    This is the load-bearing constraint that makes 'add a service
    to the example without updating the schema' a hard error at
    validation time. If a future PR loosens this to true, the
    drift-detection surface goes away and this test would have
    to be updated.
    """
    services = schema.get("properties", {}).get("services", {})
    assert services.get("additionalProperties") is False, (
        f"schema.services.additionalProperties must be False (to "
        f"catch typo'd service names); got {services.get('additionalProperties')}"
    )


# ============================================================================
# Example-level assertions
# ============================================================================


def test_example_services_block_is_object(example: dict) -> None:
    """The example's services block is an object (not a list, not a string)."""
    services = example.get("services", {})
    assert isinstance(services, dict), (
        f"example.services must be a dict; got {type(services).__name__}"
    )


def test_example_service_keys_are_in_schema_whitelist(schema: dict, example: dict) -> None:
    """Every key in example.services must be in schema.services.properties.

    This is the regression: a service key in the example that's
    NOT in the schema's whitelist means the example is invalid
    (the schema rejects unknown service keys with
    'Additional properties are not allowed'). This test catches
    the drift at PR time, not at consumer-fork validation time.
    """
    allowed = set(schema["properties"]["services"]["properties"].keys())
    actual = set(example["services"].keys())
    unknown = actual - allowed
    assert not unknown, (
        f"example.services has {len(unknown)} key(s) not in the schema's "
        f"whitelist. Either add the key to schema.services.properties "
        f"or remove it from example.cgp.yaml.\n"
        f"  Unknown: {sorted(unknown)}\n"
        f"  Schema allows: {sorted(allowed)}"
    )


# ============================================================================
# Cross-product: example validates against schema
# ============================================================================


def test_example_validates_against_schema(schema: dict, example: dict) -> None:
    """The canonical example validates cleanly against the v1 schema.

    This is the load-bearing test: jsonschema.validate() runs the
    full schema validation (required fields, type checks, the
    additionalProperties: false on services, etc.). A clean
    validation means the example is structurally compatible
    with every consumer fork that loads the bootstrap.

    If this test fails, the drift is in one of three places:
      - example.cgp.yaml has a typo / missing field
      - v1.schema.json has the wrong type or missing required field
      - the schema's services.properties whitelist doesn't
        include a key the example uses

    The first two are caught by jsonschema's own error reporting;
    the third is caught by test_example_service_keys_are_in_schema_whitelist
    with a clearer error message.
    """
    jsonschema_mod = pytest.importorskip("jsonschema")
    jsonschema_mod.validate(example, schema)


def test_schema_lists_minimax_in_services_properties(schema: dict) -> None:
    """The schema's services.properties includes 'minimax'.

    The PR #2612 fix added 'minimax' to the schema's services
    whitelist. This test pins the fix: a future PR that
    accidentally removes 'minimax' (e.g., a refactor of the
    service keys) is caught here, with a clear 'you need to
    also update example.cgp.yaml' message.
    """
    props = schema.get("properties", {}).get("services", {}).get("properties", {})
    assert "minimax" in props, (
        f"schema.services.properties must include 'minimax' (the "
        f"model cascade service added in PR #2612). Current "
        f"whitelist: {list(props.keys())}"
    )
