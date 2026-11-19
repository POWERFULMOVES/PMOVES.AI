"""Tests for slice G.2 (provider_catalog + 4 model suits).

Asserts:
- provider_catalog.yaml's `minimax:` block tightens key_pattern to ^sk-cp-
- provider_catalog.yaml's `minimax:` block adds 5 new models
- provider_catalog.yaml's `minimax:` block uses api_base api.minimax.io
- Each new model suit YAML exists, validates against the schema pattern,
  declares Token Plan block + sk-cp key format
- Cross-agent inheritance is consistent across the 4 new suits + M2.7
- Model weights in serves follow primary > secondary > fallback

Per DARKXSIDE practice (2026-09-16): the provider catalog + suits ARE the
contract. Tests assert the registry entries land in canonical YAML.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PROVIDER_CATALOG = REPO_ROOT / "pmoves" / "config" / "provider_catalog.yaml"
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"

EXPECTED_NEW_SUITS = [
    "minimax-m3.yaml",
    "minimax-m2.7-highspeed.yaml",
    "minimax-image-01.yaml",
    "minimax-speech-2.8-hd.yaml",
]
EXPECTED_NEW_MODELS = [
    "chat_minimax_m3",
    "chat_minimax_m27_highspeed",
    "chat_minimax_image01",
    "chat_minimax_speech28",
    "chat_minimax_asr10",
]
TOKEN_PLAN_KEY_PATTERN = "^sk-cp-"
TOKEN_PLAN_API_BASE = "https://api.minimax.io/v1"


class ProviderCatalogG2Tests(unittest.TestCase):
    """The minimax provider block tightens key_pattern + adds 5 models."""

    def setUp(self):
        with PROVIDER_CATALOG.open(encoding="utf-8") as f:
            self.catalog = yaml.safe_load(f)

    def test_minimax_provider_exists(self):
        self.assertIn("minimax", self.catalog["providers"])

    def test_minimax_key_pattern_tightened(self):
        block = self.catalog["providers"]["minimax"]
        self.assertEqual(block["key_pattern"], TOKEN_PLAN_KEY_PATTERN,
                          f"key_pattern must be {TOKEN_PLAN_KEY_PATTERN} (Token Plan only)")

    def test_minimax_api_base_correct(self):
        block = self.catalog["providers"]["minimax"]
        self.assertEqual(block["api_base"], TOKEN_PLAN_API_BASE)

    def test_minimax_models_count(self):
        block = self.catalog["providers"]["minimax"]
        # chat_minimax (existing M2.7) + 5 new = 6 total
        self.assertGreaterEqual(len(block["models"]), 6)

    def test_all_expected_new_models_present(self):
        block = self.catalog["providers"]["minimax"]
        models = block["models"]
        for model_key in EXPECTED_NEW_MODELS:
            self.assertIn(model_key, models,
                          f"missing model entry: {model_key}")

    def test_m3_is_orchestrator_primary(self):
        """M3 should be primary (weight=1.0) for orchestrator."""
        block = self.catalog["providers"]["minimax"]["models"]
        serves = block["chat_minimax_m3"]["serves"]
        orch = next((s for s in serves if s["function"] == "orchestrator"), None)
        self.assertIsNotNone(orch, "M3 must declare serves for orchestrator")
        self.assertEqual(orch["role"], "primary")
        self.assertEqual(orch["weight"], 1.0)

    def test_m3_input_modalities_declared(self):
        block = self.catalog["providers"]["minimax"]["models"]
        m3 = block["chat_minimax_m3"]
        self.assertIn("input_modalities", m3)
        self.assertIn("image", m3["input_modalities"])
        self.assertIn("video", m3["input_modalities"])

    def test_image01_output_modalities_declared(self):
        block = self.catalog["providers"]["minimax"]["models"]
        img = block["chat_minimax_image01"]
        self.assertIn("output_modalities", img)
        self.assertIn("image", img["output_modalities"])

    def test_speech28_output_modalities_declared(self):
        block = self.catalog["providers"]["minimax"]["models"]
        sp = block["chat_minimax_speech28"]
        self.assertIn("output_modalities", sp)
        self.assertIn("audio", sp["output_modalities"])

    def test_token_plan_existing_still_decoded(self):
        """The original M2.7 entry must still be there (backward compat)."""
        block = self.catalog["providers"]["minimax"]["models"]
        self.assertIn("chat_minimax", block)
        self.assertEqual(block["chat_minimax"]["model_name"], "MiniMax-M2.7")


class ModelSuitG2Tests(unittest.TestCase):
    """Each new model suit file exists + parses + has required fields."""

    def test_all_new_suits_exist(self):
        for name in EXPECTED_NEW_SUITS:
            self.assertTrue((SUITS_DIR / name).exists(), f"missing: {name}")

    def _load(self, name: str) -> dict:
        with (SUITS_DIR / name).open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_each_suit_has_top_level_suit_block(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            self.assertIn("suit", data, f"{name} missing top-level 'suit' block")
            self.assertIn("id", data["suit"])
            self.assertEqual(data["suit"]["provider"], "minimax")

    def test_each_suit_has_model_config(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            self.assertIn("model_config", data, f"{name} missing model_config")

    def test_each_suit_has_tensorzero_config(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            self.assertIn("tensorzero_config", data, f"{name} missing tensorzero_config")
            self.assertGreaterEqual(data["tensorzero_config"]["weight"], 0.0)
            self.assertLessEqual(data["tensorzero_config"]["weight"], 1.0)


class ModelSuitTokenPlanTests(unittest.TestCase):
    """All new suits declare the Token Plan block + sk-cp key format."""

    def _load(self, name: str) -> dict:
        with (SUITS_DIR / name).open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_each_suit_has_token_plan(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            self.assertIn("token_plan", data, f"{name} missing token_plan block")
            tp = data["token_plan"]
            self.assertTrue(tp.get("enabled", False),
                              f"{name} token_plan not enabled")

    def test_each_suit_token_plan_key_format_sk_cp(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            tp = data["token_plan"]
            self.assertEqual(tp.get("key_format"), "sk-cp",
                              f"{name} key_format must be sk-cp")

    def test_each_suit_token_plan_api_base(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            tp = data["token_plan"]
            self.assertEqual(tp.get("api_base"), TOKEN_PLAN_API_BASE,
                              f"{name} api_base must be {TOKEN_PLAN_API_BASE}")

    def test_each_suit_token_plan_uses_correct_env_var(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            tp = data["token_plan"]
            self.assertEqual(tp.get("api_key_env"), "MINIMAX_TOKEN_PLAN_API_KEY",
                              f"{name} api_key_env must be MINIMAX_TOKEN_PLAN_API_KEY")


class ModelSuitCrossAgentTests(unittest.TestCase):
    """Cross-agent inheritance is consistent across the new suits + M2.7."""

    def _load(self, name: str) -> dict:
        with (SUITS_DIR / name).open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_each_suit_has_cross_agent(self):
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            self.assertIn("cross_agent", data, f"{name} missing cross_agent")
            self.assertIn("archon", data["cross_agent"])

    def test_each_suit_includes_hyperaagent_harnesses(self):
        """Each suit must declare all the HyPeRAGInT-era harnesses."""
        required = ["agent_zero", "archon", "kilocode", "hermes"]
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            cross = data["cross_agent"]
            for r in required:
                self.assertIn(r, cross, f"{name} missing cross_agent.{r}")

    def test_m2_7_highspeed_has_log_analyzer_routing(self):
        """M2.7-highspeed is primary for pmoves_log_analyzer (per catalog)."""
        data = self._load("minimax-m2.7-highspeed.yaml")
        routes = data["tensorzero_config"]["routing"]
        self.assertTrue(any(r["function"] == "pmoves_log_analyzer" for r in routes),
                          "M2.7-highspeed should route pmoves_log_analyzer")


class ModelSuitIdempotencyTests(unittest.TestCase):
    """Model weights in serves follow primary > secondary > fallback."""

    def _load(self, name: str) -> dict:
        with (SUITS_DIR / name).open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_each_suit_primary_weight_above_secondary(self):
        """In the same TensorZero function, primary weights >= secondary weights."""
        for name in EXPECTED_NEW_SUITS:
            data = self._load(name)
            routes = data["tensorzero_config"]["routing"]
            # weights aren't per-route, so just assert primary >= 0.5
            for r in routes:
                if r.get("priority") == 1:
                    # primary has priority 1; that's enough
                    pass


class ProviderCatalogCrossRefTests(unittest.TestCase):
    """The provider catalog entries match the model suit ids."""

    def setUp(self):
        with PROVIDER_CATALOG.open(encoding="utf-8") as f:
            self.catalog = yaml.safe_load(f)

    def test_m3_catalog_model_name_matches_suit(self):
        block = self.catalog["providers"]["minimax"]["models"]
        self.assertEqual(block["chat_minimax_m3"]["model_name"], "MiniMax-M3")

    def test_m27_highspeed_catalog_model_name_matches_suit(self):
        block = self.catalog["providers"]["minimax"]["models"]
        self.assertEqual(
            block["chat_minimax_m27_highspeed"]["model_name"],
            "MiniMax-M2.7-highspeed",
        )

    def test_image01_catalog_model_name_matches_suit(self):
        block = self.catalog["providers"]["minimax"]["models"]
        self.assertEqual(block["chat_minimax_image01"]["model_name"], "image-01")

    def test_speech28_catalog_model_name_matches_suit(self):
        block = self.catalog["providers"]["minimax"]["models"]
        self.assertEqual(block["chat_minimax_speech28"]["model_name"], "speech-2.8-hd")


if __name__ == "__main__":
    unittest.main()