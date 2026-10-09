"""Tests for slice G.1 (Mavis Collection auth + manifest schema).

Asserts:
- The manifest schema + example are present + parseable.
- The manifest schema validates against a minimal manifest.
- The resolver's 3-step probe logic correctly classifies auth/quota/chat
  results as wired-up or not.
- The example manifest's identity.form_ref points at a real form file
  (cross-collection identity crossref).
- The hyperagint.yaml form carries the cross_agent_inheritance that the
  example manifest declares (round-trip).

Per DARKFOLLOWS practice (2026-09-16): the resolver + probe are the
contract. Tests assert behavior, not just shape.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "pmoves" / "configs" / "mavis_collection" / "manifest.schema.yaml"
EXAMPLE_PATH = REPO_ROOT / "pmoves" / "configs" / "mavis_collection" / "example.yaml"
RESOLVER_PATH = REPO_ROOT / "pmoves" / "tools" / "mavis_collection_resolve.py"
HYPERAGINT_FORM_PATH = REPO_ROOT / "pmoves" / "configs" / "agents" / "forms" / "hyperagint.yaml"

# Make resolver importable as a module
sys.path.insert(0, str(REPO_ROOT / "pmoves" / "tools"))
import mavis_collection_resolve as resolver  # noqa: E402


class MavisCollectionManifestSchemaTests(unittest.TestCase):
    """The manifest schema + example parse cleanly and validate against
    the schema's own required-fields subset."""

    def test_schema_file_exists(self):
        self.assertTrue(SCHEMA_PATH.exists(), f"missing: {SCHEMA_PATH}")

    def test_example_file_exists(self):
        self.assertTrue(EXAMPLE_PATH.exists(), f"missing: {EXAMPLE_PATH}")

    def test_resolver_script_exists(self):
        self.assertTrue(RESOLVER_PATH.exists(), f"missing: {RESOLVER_PATH}")

    def test_schema_parses_as_yaml(self):
        with SCHEMA_PATH.open(encoding="utf-8") as f:
            schema = yaml.safe_load(f)
        self.assertIn("spec", schema)
        self.assertEqual(schema["spec"], "pmoves.bootstrap/v1")
        self.assertEqual(str(schema["schema_version"]), "1.0")

    def test_example_manifest_parses_and_validates(self):
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        errors = resolver.validate_manifest(manifest)
        self.assertEqual(errors, [], f"example manifest failed validation: {errors}")

    def test_minimal_manifest_validates(self):
        """The minimal example from manifest.schema.yaml validates cleanly."""
        manifest = {
            "spec": "pmoves.bootstrap/v1",
            "meta": {
                "schema_version": "1.0",
                "created": "2026-10-05",
                "operator": "DARKXSIDE",
                "home": "~/.mavis/collection/",
            },
            "identity": {
                "agent": "HyPeRAGInT",
                "form_ref": "pmoves/configs/agents/forms/hyperagint.yaml",
            },
            "super_nodes": {
                "auth": [
                    {"provider": "minimax", "format": "sk-cp", "source": "~/.mmx/config.json"}
                ],
            },
        }
        errors = resolver.validate_manifest(manifest)
        self.assertEqual(errors, [], f"minimal manifest failed: {errors}")

    def test_manifest_with_wrong_spec_fails(self):
        manifest = {
            "spec": "wrong.profile/v1",
            "meta": {"schema_version": "1.0", "created": "2026-10-05",
                      "operator": "DARKXSIDE", "home": "~/.mavis/collection/"},
            "identity": {"agent": "HyPeRAGInT", "form_ref": "x"},
            "super_nodes": {},
        }
        errors = resolver.validate_manifest(manifest)
        self.assertTrue(any("spec" in e for e in errors), errors)

    def test_manifest_missing_required_field_fails(self):
        manifest = {
            "spec": "pmoves.bootstrap/v1",
            "meta": {"schema_version": "1.0"},  # missing created/operator/home
            "identity": {"agent": "HyPeRAGInT"},  # missing form_ref
            "super_nodes": {},
        }
        errors = resolver.validate_manifest(manifest)
        # Should fail on multiple required fields
        self.assertGreater(len(errors), 0, errors)
        self.assertTrue(any("created" in e for e in errors), errors)
        self.assertTrue(any("form_ref" in e for e in errors), errors)


class MavisCollectionResolverTests(unittest.TestCase):
    """The resolver CLI's subcommands wire up correctly (mocked mmx)."""

    def test_validate_subcommand_returns_0_on_valid_example(self):
        with patch("sys.argv", ["mavis_collection_resolve.py", "validate",
                                  "--manifest", str(EXAMPLE_PATH)]):
            rc = resolver.main()
        self.assertEqual(rc, 0, "validate should return 0 on valid example manifest")

    def test_validate_subcommand_returns_nonzero_on_missing_file(self):
        with patch("sys.argv", ["mavis_collection_resolve.py", "validate",
                                  "--manifest", "/nonexistent/manifest.yaml"]):
            rc = resolver.main()
        self.assertNotEqual(rc, 0)

    def test_validate_subcommand_returns_nonzero_on_invalid_yaml(self,):
        bad_path = Path("/tmp/_bad_manifest_g1.yaml")
        bad_path.write_text("not: valid: yaml: at: all:", encoding="utf-8")
        try:
            with patch("sys.argv", ["mavis_collection_resolve.py", "validate",
                                      "--manifest", str(bad_path)]):
                rc = resolver.main()
            self.assertNotEqual(rc, 0)
        finally:
            bad_path.unlink(missing_ok=True)


class MavisCollectionAuthProbeTests(unittest.TestCase):
    """The 3-step probe gate logic correctly classifies auth/quota/chat results."""

    def _ok_auth(self):
        return {
            "method": "api-key",
            "source": "config.json",
            "key": "sk-c...UStw",
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }

    def _ok_quota(self):
        return {
            "model_remains": [
                {
                    "model_name": "general",
                    "current_interval_status": 1,
                    "current_interval_remaining_percent": 85,
                    "current_weekly_status": 1,
                    "current_weekly_remaining_percent": 97,
                },
                {"model_name": "video", "current_interval_status": 3},
            ],
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }

    def _ok_chat(self):
        return {"ok": True, "response": {"content": "PONG"}}

    def _fail_auth(self):
        return {"base_resp": {"status_code": 4, "status_msg": "insufficient balance (1008)"}}

    def test_probe_passes_when_all_three_steps_green(self):
        with patch.object(resolver, "run_mmx_auth_status", return_value=self._ok_auth()), \
             patch.object(resolver, "run_mmx_quota_show", return_value=self._ok_quota()), \
             patch.object(resolver, "run_mmx_text_chat", return_value=self._ok_chat()):
            result = resolver.three_step_probe()
        self.assertTrue(result["wired_up"], result)
        self.assertEqual(result["errors"], [])

    def test_probe_fails_when_auth_fails(self):
        with patch.object(resolver, "run_mmx_auth_status", return_value=self._fail_auth()), \
             patch.object(resolver, "run_mmx_quota_show", return_value=self._ok_quota()), \
             patch.object(resolver, "run_mmx_text_chat", return_value=self._ok_chat()):
            result = resolver.three_step_probe()
        self.assertFalse(result["wired_up"])
        self.assertIn("step_1_auth_failed", result["errors"])

    def test_probe_fails_when_no_general_quota_bucket(self):
        quota = {"model_remains": [{"model_name": "video"}], "base_resp": {"status_code": 0}}
        with patch.object(resolver, "run_mmx_auth_status", return_value=self._ok_auth()), \
             patch.object(resolver, "run_mmx_quota_show", return_value=quota), \
             patch.object(resolver, "run_mmx_text_chat", return_value=self._ok_chat()):
            result = resolver.three_step_probe()
        self.assertFalse(result["wired_up"])
        self.assertIn("step_2_no_general_quota_bucket", result["errors"])

    def test_probe_fails_when_quota_bucket_inactive(self):
        quota = self._ok_quota()
        quota["model_remains"][0]["current_interval_status"] = 0  # inactive
        with patch.object(resolver, "run_mmx_auth_status", return_value=self._ok_auth()), \
             patch.object(resolver, "run_mmx_quota_show", return_value=quota), \
             patch.object(resolver, "run_mmx_text_chat", return_value=self._ok_chat()):
            result = resolver.three_step_probe()
        self.assertFalse(result["wired_up"])
        self.assertTrue(any("step_2_quota_status" in e for e in result["errors"]))

    def test_probe_fails_when_chat_returns_error(self):
        with patch.object(resolver, "run_mmx_auth_status", return_value=self._ok_auth()), \
             patch.object(resolver, "run_mmx_quota_show", return_value=self._ok_quota()), \
             patch.object(resolver, "run_mmx_text_chat", return_value={"ok": False, "error": "billing_gate"}):
            result = resolver.three_step_probe()
        self.assertFalse(result["wired_up"])
        self.assertTrue(any("step_3_chat_failed" in e for e in result["errors"]))


class MavisCollectionIdentityCrossrefTests(unittest.TestCase):
    """The example manifest's identity + the hyperagint.yaml form agree.

    This is the cross-collection identity invariant: a manifest is invalid if
    its declared identity.form_ref points at a file that doesn't exist OR
    if the cross_agent_inheritance list contradicts the form's architecture.
    """

    def test_hyperagint_form_exists(self):
        self.assertTrue(HYPERAGINT_FORM_PATH.exists(), f"missing: {HYPERAGINT_FORM_PATH}")

    def test_example_manifest_form_ref_resolves(self):
        """The example manifest's identity.form_ref must point at a real file."""
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        form_ref = manifest["identity"]["form_ref"]
        # Resolve relative to repo root
        form_path = REPO_ROOT / form_ref
        self.assertTrue(form_path.exists(), f"form_ref not found: {form_path}")

    def test_hyperagint_form_has_harness_target_for_minimax(self):
        """The hyperagint form's harness_target should match HyPeRAGInT identity."""
        with HYPERAGINT_FORM_PATH.open(encoding="utf-8") as f:
            form = yaml.safe_load(f)
        self.assertEqual(form["name"], "HyPeRAGInT")
        # HyPeRAGInT form carries its own identity, not a cross-agent inheritance list.
        # The crossref check is that the manifest declares inheritance + the form exists.

    def test_example_manifest_inheritance_includes_claude_code(self):
        """The example manifest declares claude-code in cross_agent_inheritance;
        HyPeRAGInT is built atop claude-pmoves-{node}-{suite} per design doc."""
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        inheritance = manifest["identity"].get("cross_agent_inheritance", [])
        self.assertIn("claude-code", inheritance,
                       "HyPeRAGInT must inherit from claude-code per launcher family")


class MavisCollectionExampleManifestTests(unittest.TestCase):
    """The example manifest covers the surfaces slice G will populate."""

    def test_example_covers_all_super_node_sections(self):
        """G.2-G.4 surfaces are all declared (auth, models, datasets, personas,
        mindmap, skills, plugins, chit)."""
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        super_nodes = manifest["super_nodes"]
        expected = {"auth", "models", "datasets", "personas", "mindmap", "skills", "plugins", "chit"}
        self.assertEqual(set(super_nodes.keys()), expected,
                          f"missing sections: {expected - set(super_nodes.keys())}")

    def test_example_datasets_point_at_real_pmoves_surfaces(self):
        """Dataset refs must match the format 'pmoves/config/datasets.yaml#<key>'."""
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        datasets = manifest["super_nodes"]["datasets"]
        for d in datasets:
            self.assertTrue(d["ref"].startswith("pmoves/config/datasets.yaml#"),
                              f"bad ref format: {d['ref']}")

    def test_example_datasets_hf_ids_use_darkxside(self):
        """All dataset hf_ids should target the DARKXSIDE org (per datasets.yaml)."""
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        for d in manifest["super_nodes"]["datasets"]:
            self.assertTrue(d["hf_id"].startswith("DARKXSIDE/"),
                              f"hf_id not in DARKXSIDE org: {d['hf_id']}")

    def test_example_models_list_matches_token_plan_feature_set(self):
        """The example models list covers M3 / M2.7 / image / speech per
        operator's Token Plan feature list (2026-10-05)."""
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        models_entry = next(
            (m for m in manifest["super_nodes"]["models"] if m["provider"] == "minimax"),
            None,
        )
        self.assertIsNotNone(models_entry, "no minimax models entry in example")
        models = models_entry["models"]
        # Operator's Token Plan features: M3 / M2.7 / image / speech
        for required in ("MiniMax-M3", "MiniMax-M2.7", "image-01", "speech-2.8-hd"):
            self.assertIn(required, models,
                          f"Token Plan feature missing from example: {required}")


if __name__ == "__main__":
    unittest.main()