"""Smoke tests for pmoves.tools.load_bootstrap.

Mock-free - the CGP is loaded from the real example file in the repo
(pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml), so the
tests prove the schema, the example, and the loader are all in sync.
Run with:
    python -m pytest pmoves/tools/tests/test_load_bootstrap.py -v
or:
    python -m unittest pmoves.tools.tests.test_load_bootstrap
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pmoves.tools.load_bootstrap import (  # noqa: E402
    DEFAULT_CGP_PATH,
    ENV_VAR_CGP,
    ENV_VAR_CGP_PATH,
    SCHEMA_PATH,
    Bootstrap,
    BootstrapError,
    Identity,
    Services,
    load_bootstrap,
    load_bootstrap_raw,
)


class LoadFromExampleTests(unittest.TestCase):
    """The example CGP in the repo is the canonical reference. The loader
    should be able to read it, validate it, and produce a Bootstrap."""

    def setUp(self) -> None:
        # Clear any env vars the previous test may have set
        for k in (ENV_VAR_CGP, ENV_VAR_CGP_PATH):
            os.environ.pop(k, None)
        # Clear any PMOVES_BOOTSTRAP_* env vars from a previous test
        for k in list(os.environ.keys()):
            if k.startswith("PMOVES_BOOTSTRAP_"):
                del os.environ[k]

    def test_loads_default_example(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertIsInstance(bs, Bootstrap)
        self.assertEqual(bs.spec, "pmoves.bootstrap/v1")

    def test_identity_block(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertEqual(bs.identity.agent, "minimax")
        self.assertEqual(bs.identity.role, "implementer")
        self.assertEqual(bs.identity.skin, "dimensional")

    def test_tools_list(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertIn("mavis__agent__create", bs.tools)
        self.assertIn("comfyui_client", bs.tools)
        self.assertIn("render_skin", bs.tools)

    def test_mcps_list(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertIn("pmoves-nats-mcp", bs.mcps)
        self.assertIn("pmoves-chit-sign", bs.mcps)

    def test_services_advisory(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertEqual(bs.services.tailscale.get("host"), "powerfullmoves.tail.ts.net")
        self.assertIn("pixel-10-xl-1", bs.services.rustdesk.get("devices", []))
        self.assertEqual(bs.services.hostinger.get("status"), "pending-mgmt")
        self.assertEqual(bs.services.cloudflare.get("account"), "powerfullmoves")

    def test_routing_targets(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertEqual(bs.routing.kiloclaw.get("target"), "glm-5.1")
        self.assertEqual(bs.routing.hermes.get("target"), "hermes-3")

    def test_constraints_present(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertIn("no-override-existing-config", bs.constraints)
        self.assertIn("no-chit-bypass", bs.constraints)
        self.assertIn("preserve-existing-tools", bs.constraints)

    def test_has_constraint_predicate(self) -> None:
        bs = load_bootstrap(export_env=False)
        self.assertTrue(bs.has_constraint("no-chit-bypass"))
        self.assertFalse(bs.has_constraint("not-a-real-constraint"))


class LoadFromSourceTests(unittest.TestCase):
    """Loading from a raw string (env var or source arg)."""

    def setUp(self) -> None:
        for k in (ENV_VAR_CGP, ENV_VAR_CGP_PATH):
            os.environ.pop(k, None)

    def test_load_from_yaml_string(self) -> None:
        cgp = """
spec: pmoves.bootstrap/v1
meta:
  created_at: "2026-08-08T00:00:00Z"
  operator: darkxside
  source: test
identity:
  agent: minimax
  role: critic
  skin: companion
tools: [mavis__agent__create]
mcps: [pmoves-nats-mcp]
services:
  tailscale:
    host: test.tail.ts.net
routing:
  hermes:
    target: hermes-3
constraints: [no-chit-bypass]
"""
        bs = load_bootstrap(source=cgp, export_env=False)
        self.assertEqual(bs.identity.role, "critic")
        self.assertEqual(bs.identity.skin, "companion")
        self.assertEqual(bs.services.tailscale.get("host"), "test.tail.ts.net")
        self.assertEqual(bs.routing.hermes.get("target"), "hermes-3")

    def test_load_from_json_string(self) -> None:
        cgp = json.dumps({
            "spec": "pmoves.bootstrap/v1",
            "meta": {"created_at": "2026-08-08T00:00:00Z", "operator": "darkxside", "source": "test"},
            "identity": {"agent": "minimax", "role": "renderer"},
            "tools": ["render_skin"],
            "mcps": [],
            "services": {},
            "routing": {},
            "constraints": [],
        })
        bs = load_bootstrap(source=cgp, export_env=False)
        self.assertEqual(bs.identity.role, "renderer")
        self.assertEqual(bs.tools, ["render_skin"])

    def test_load_from_env_var(self) -> None:
        os.environ[ENV_VAR_CGP] = (
            "spec: pmoves.bootstrap/v1\n"
            "meta: {created_at: '2026-08-08T00:00:00Z', operator: darkxside, source: test}\n"
            "identity: {agent: minimax, role: curator}\n"
            "tools: []\n"
            "mcps: []\n"
            "services: {}\n"
            "routing: {}\n"
            "constraints: []\n"
        )
        bs = load_bootstrap(export_env=False)
        self.assertEqual(bs.identity.role, "curator")

    def test_explicit_path_overrides_env(self) -> None:
        # Set an env var with a wrong spec; explicit path should win
        os.environ[ENV_VAR_CGP] = "spec: wrong\nmeta: {}\nidentity: {}\ntools: []\n"
        bs = load_bootstrap(path=DEFAULT_CGP_PATH, export_env=False)
        self.assertEqual(bs.spec, "pmoves.bootstrap/v1")


class ValidationFailureTests(unittest.TestCase):
    """The CGP must pass schema validation. These tests feed bad CGPs
    and expect BootstrapError."""

    def setUp(self) -> None:
        for k in (ENV_VAR_CGP, ENV_VAR_CGP_PATH):
            os.environ.pop(k, None)

    def test_wrong_spec_value_rejected(self) -> None:
        cgp = {
            "spec": "wrong.spec/v9",
            "meta": {"created_at": "2026-08-08T00:00:00Z", "operator": "darkxside", "source": "test"},
            "identity": {"agent": "minimax", "role": "implementer"},
            "tools": [], "mcps": [], "services": {}, "routing": {}, "constraints": [],
        }
        with self.assertRaises(BootstrapError) as ctx:
            load_bootstrap_raw(cgp, export_env=False)
        self.assertIn("pmoves.bootstrap/v1", str(ctx.exception))

    def test_missing_required_field_rejected(self) -> None:
        cgp = {
            "spec": "pmoves.bootstrap/v1",
            "meta": {"created_at": "2026-08-08T00:00:00Z", "operator": "darkxside", "source": "test"},
            "identity": {"agent": "minimax", "role": "implementer"},
            # tools is missing
            "mcps": [], "services": {}, "routing": {}, "constraints": [],
        }
        with self.assertRaises(BootstrapError) as ctx:
            load_bootstrap_raw(cgp, export_env=False)
        self.assertIn("tools", str(ctx.exception))

    def test_identity_missing_agent_rejected(self) -> None:
        cgp = {
            "spec": "pmoves.bootstrap/v1",
            "meta": {"created_at": "2026-08-08T00:00:00Z", "operator": "darkxside", "source": "test"},
            "identity": {"role": "implementer"},  # agent missing
            "tools": [], "mcps": [], "services": {}, "routing": {}, "constraints": [],
        }
        with self.assertRaises(BootstrapError):
            load_bootstrap_raw(cgp, export_env=False)

    def test_empty_super_nodes_required_by_schema(self) -> None:
        cgp = {
            "spec": "pmoves.bootstrap/v1",
            "meta": {"created_at": "2026-08-08T00:00:00Z", "operator": "darkxside", "source": "test"},
            "identity": {"agent": "minimax", "role": "implementer"},
            "tools": [], "mcps": [], "services": {}, "routing": {}, "constraints": [],
            "super_nodes": [],  # required by schema
        }
        bs = load_bootstrap_raw(cgp, export_env=False)
        self.assertEqual(bs.spec, "pmoves.bootstrap/v1")


class ExportEnvTests(unittest.TestCase):
    """export_env writes PMOVES_BOOTSTRAP_* env vars so the rest of the
    session can consume the CGP via env."""

    def setUp(self) -> None:
        for k in list(os.environ.keys()):
            if k.startswith("PMOVES_BOOTSTRAP_"):
                del os.environ[k]

    def test_export_env_basic(self) -> None:
        bs = load_bootstrap(export_env=True)
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_AGENT"), "minimax")
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_ROLE"), "implementer")
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_SKIN"), "dimensional")
        self.assertIn("mavis__agent__create", os.environ.get("PMOVES_BOOTSTRAP_TOOLS", ""))
        self.assertIn("pmoves-nats-mcp", os.environ.get("PMOVES_BOOTSTRAP_MCPS", ""))

    def test_export_env_services(self) -> None:
        bs = load_bootstrap(export_env=True)
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_TAILSCALE_HOST"), "powerfullmoves.tail.ts.net")
        self.assertIn("pixel-10-xl-1", os.environ.get("PMOVES_BOOTSTRAP_RUSTDESK_DEVICES", ""))
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_HOSTINGER_SITE"), "powerfullmoves.com")
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_CLOUDFLARE_ACCOUNT"), "powerfullmoves")

    def test_export_env_routing(self) -> None:
        bs = load_bootstrap(export_env=True)
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_TARGET_KILOCLAW"), "glm-5.1")
        self.assertEqual(os.environ.get("PMOVES_BOOTSTRAP_TARGET_HERMES"), "hermes-3")

    def test_export_env_skipped_when_disabled(self) -> None:
        load_bootstrap(export_env=False)
        self.assertNotIn("PMOVES_BOOTSTRAP_AGENT", os.environ)


class SchemaSyncTests(unittest.TestCase):
    """The example.cgp.yaml in the repo must validate against the
    v1.schema.json. If this test fails, either the schema or the
    example drifted and the harness's downstream consumers will break."""

    def test_example_validates_against_schema(self) -> None:
        from pmoves.tools.load_bootstrap import _read_cgp, _load_schema, _validate
        cgp = _read_cgp(DEFAULT_CGP_PATH)
        schema = _load_schema()
        # Should not raise
        _validate(cgp, schema)
        self.assertEqual(cgp["spec"], "pmoves.bootstrap/v1")

    def test_schema_file_exists(self) -> None:
        self.assertTrue(Path(SCHEMA_PATH).exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
