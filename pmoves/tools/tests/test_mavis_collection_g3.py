"""Tests for slice G.3 (Mavis Collection personas + datasets).

Asserts:
- The persona YAMLs exist and validate against the schema's `super_nodes.personas` shape.
- The dataset manifest pointers exist and reference real PMOVES surfaces.
- The example manifest's datasets[1] (pmoves-chit-multimodal) carries the operator-specified
  YouTube playlist + Drive account refs.
- The persona YAMLs declare pointer-only contracts.
- Cross-agent inheritance is consistent across personas + the example manifest.

Per DARKXSIDE practice (2026-09-16): the manifest pointers ARE the contract.
Tests assert the schema + operator-specified IDs land in the YAML.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PERSONAS_DIR = REPO_ROOT / "pmoves" / "configs" / "mavis_collection" / "personas"
DATASETS_DIR = REPO_ROOT / "pmoves" / "configs" / "mavis_collection" / "datasets"
EXAMPLE_PATH = REPO_ROOT / "pmoves" / "configs" / "mavis_collection" / "example.yaml"

OPERATOR_PLAYLIST_ID = "PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8"
OPERATOR_DRIVE_ACCOUNT = "cataclysmstudios@gmail.com"
OPERATOR_YT_CHANNEL = "@PMOVESAI"


class PersonaFileTests(unittest.TestCase):
    """Each persona file exists + has the schema's required fields."""

    def test_fl00_exists(self):
        self.assertTrue((PERSONAS_DIR / "fl00.yaml").exists())

    def test_darkxside_exists(self):
        self.assertTrue((PERSONAS_DIR / "darkxside.yaml").exists())

    def test_mavis_orchestrator_exists(self):
        self.assertTrue((PERSONAS_DIR / "mavis-orchestrator.yaml").exists())

    def _load(self, name: str) -> dict:
        with (PERSONAS_DIR / name).open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_fl00_signature_moves_present(self):
        data = self._load("fl00.yaml")
        self.assertEqual(data["name"], "fl00")
        # Operator's signature moves ("care bear stares + DARKXSIDE shifts")
        moves = data.get("signature_moves", [])
        self.assertTrue(any("care" in m.lower() for m in moves),
                          "fl00.yaml must declare care-bear signature move")

    def test_darkxside_going_public(self):
        data = self._load("darkxside.yaml")
        self.assertEqual(data["name"], "darkxside")
        # Operator directive 2026-08-07: real identity
        self.assertTrue(data.get("public_identity", False),
                          "darkxside.yaml must declare public_identity=true")
        # YouTube channel + playlist
        self.assertEqual(data["youtube"]["channel"], OPERATOR_YT_CHANNEL)
        self.assertEqual(data["youtube"]["primary_playlist"], OPERATOR_PLAYLIST_ID)

    def test_mavis_orchestrator_token_plan_envelope(self):
        data = self._load("mavis-orchestrator.yaml")
        self.assertEqual(data["name"], "mavis-orchestrator")
        # 1M context window + token plan envelope
        self.assertEqual(data["token_plan"]["context_window"], 1000000)
        self.assertEqual(data["token_plan"]["provider"], "minimax")
        # Backbone should include local + cloud
        self.assertIn("offline", data["backbone"])
        self.assertIn("cloud", data["backbone"])

    def test_all_personas_pointer_only(self):
        for name in ("fl00.yaml", "darkxside.yaml", "mavis-orchestrator.yaml"):
            data = self._load(name)
            self.assertTrue(data.get("pointer_only", False),
                              f"{name} must declare pointer_only=true")


class DatasetManifestTests(unittest.TestCase):
    """Each dataset manifest pointer exists + carries operator-specified refs."""

    def test_pmoves_chit_multimodal_exists(self):
        self.assertTrue((DATASETS_DIR / "pmoves-chit-multimodal.yaml").exists())

    def test_pmoves_chit_text_exists(self):
        self.assertTrue((DATASETS_DIR / "pmoves-chit-text.yaml").exists())

    def test_pmoves_agent_traces_exists(self):
        self.assertTrue((DATASETS_DIR / "pmoves-agent-traces.yaml").exists())

    def test_pmoves_chit_multimodal_playlist_ref(self):
        with (DATASETS_DIR / "pmoves-chit-multimodal.yaml").open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # Operator's YouTube playlist is the canonical multimodal source
        self.assertEqual(data["primary_ingestion"]["playlist_id"], OPERATOR_PLAYLIST_ID)
        self.assertEqual(data["primary_ingestion"]["channel"], OPERATOR_YT_CHANNEL)
        self.assertEqual(data["primary_ingestion"]["account"], OPERATOR_DRIVE_ACCOUNT)
        # PMOVES.YT and pmoves.yt_mini both declared
        service_names = [s["name"] for s in data["primary_ingestion"]["services"]]
        self.assertIn("PMOVES.YT", service_names)
        self.assertIn("pmoves.yt_mini", service_names)

    def test_pmoves_chit_multimodal_no_hardcoded_count(self):
        """The manifest must NOT hardcode item_count -- resolver fetches live."""
        with (DATASETS_DIR / "pmoves-chit-multimodal.yaml").open(encoding="utf-8") as f:
            text = f.read()
        # No `item_count: <integer>` outside the playlist_growth history block
        # (those are snapshots, not live counts)
        import re
        # Count occurrences of `item_count:` -- should only appear in `playlist_growth` history
        matches = re.findall(r"^\s*item_count:\s*\d+", text, re.MULTILINE)
        # The history block uses `count:` not `item_count:`
        self.assertEqual(len(matches), 0,
                          "pmoves-chit-multimodal.yaml must not hardcode item_count")

    def test_pmoves_chit_text_uses_canonical_ref(self):
        with (DATASETS_DIR / "pmoves-chit-text.yaml").open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertTrue(data["canonical_ref"].startswith("pmoves/config/datasets.yaml#"))

    def test_pmoves_agent_traces_mavis_field(self):
        with (DATASETS_DIR / "pmoves-agent-traces.yaml").open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIn("mavis_traces", data)
        self.assertEqual(data["mavis_traces"]["harness"], "mavis")


class ExampleManifestG3Tests(unittest.TestCase):
    """The example manifest's G.3 surface uses operator-specified IDs."""

    def test_example_references_all_personas(self):
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        refs = {p["ref"] for p in data["super_nodes"]["personas"]}
        self.assertIn("personas/fl00.yaml", refs)
        self.assertIn("personas/darkxside.yaml", refs)
        self.assertIn("personas/mavis-orchestrator.yaml", refs)

    def test_example_references_all_datasets(self):
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # 3 dataset entries
        self.assertEqual(len(data["super_nodes"]["datasets"]), 3)

    def test_example_datasets_carry_playlist_id(self):
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # pmoves-chit-multimodal entry should carry the playlist
        mm_entry = next(
            d for d in data["super_nodes"]["datasets"]
            if "multimodal" in d["ref"]
        )
        self.assertEqual(
            mm_entry["source_playlist"]["id"], OPERATOR_PLAYLIST_ID
        )

    def test_example_drive_references_present(self):
        with EXAMPLE_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIn("drive_references", data)
        self.assertEqual(data["drive_references"]["account"], OPERATOR_DRIVE_ACCOUNT)
        self.assertEqual(data["drive_references"]["account_alias"], "googledrive_mettle-automa")


class CrossPersonaConsistencyTests(unittest.TestCase):
    """Cross-references between personas + example manifest are consistent."""

    def test_fl00_inherits_darkxside(self):
        with (PERSONAS_DIR / "fl00.yaml").open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIn("darkxside", data["cross_agent_inheritance"],
                       "fl00.yaml must inherit darkxside per operator's signature move description")

    def test_darkxside_inherits_fl00(self):
        with (PERSONAS_DIR / "darkxside.yaml").open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertIn("fl00", data["cross_agent_inheritance"],
                       "darkxside.yaml must reference fl00 (the DARKXSIDE-shifted signature)")


if __name__ == "__main__":
    unittest.main()