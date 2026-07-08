"""CI validation for pmoves/configs/flare-model-namespace.yaml.

Ensures every Flare model namespace mapping has the required fields,
follows the pmoves/<model> naming convention, and uses known providers,
lanes, and node identifiers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "pmoves" / "configs" / "flare-model-namespace.yaml"

# Enumerated valid values — update when the fleet or provider list grows.
VALID_PROVIDERS = {
    "zai",
    "anthropic",
    "openai",
    "ollama",
    "ollama_spark",
    "nvidia_nim",
    "llamacpp_rocm",
    "huggingface",
    "nemo",
}

VALID_LANES = {"coding_plan", "cloud", "local", "edge"}

# Node identifiers are stored as YAML bare values which may parse as ints.
VALID_NODES = {"5090", "4090", "z890", "dgx-spark", "rdna4", "jetson"}


def _norm_node(val) -> str:
    """Normalise a YAML node identifier to string."""
    return str(val)


@pytest.fixture(scope="module")
def flare_config() -> dict:
    """Load and parse the flare model namespace YAML."""
    if not CONFIG_PATH.exists():
        pytest.skip(f"{CONFIG_PATH} not present")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "Top-level YAML must be a mapping"
    return data


@pytest.fixture(scope="module")
def mappings(flare_config: dict) -> dict[str, dict]:
    """Extract the mappings dict from the config."""
    assert "mappings" in flare_config, "Config missing 'mappings' key"
    m = flare_config["mappings"]
    assert isinstance(m, dict), "'mappings' must be a dict"
    assert len(m) > 0, "'mappings' must not be empty"
    return m


# ---------------------------------------------------------------------------
# Structural / top-level checks
# ---------------------------------------------------------------------------

class TestConfigStructure:
    def test_config_file_exists(self) -> None:
        assert CONFIG_PATH.exists(), f"{CONFIG_PATH} should exist"

    def test_namespace_is_pmoves(self, flare_config: dict) -> None:
        assert flare_config.get("namespace") == "pmoves"

    def test_separator_is_slash(self, flare_config: dict) -> None:
        assert flare_config.get("separator") == "/"

    def test_mappings_dict_present(self, flare_config: dict) -> None:
        assert isinstance(flare_config.get("mappings"), dict)
        assert len(flare_config["mappings"]) > 0


# ---------------------------------------------------------------------------
# Per-mapping validation
# ---------------------------------------------------------------------------

class TestMappingFields:
    """Validate every entry inside mappings has correct required and typed fields."""

    # Every mapping must declare at least one model identifier.
    REQUIRED_FIELDS = {"flare_name", "provider", "lane", "nodes"}
    IDENTIFIER_FIELDS = {"model_id", "hf_id"}

    def test_all_mappings_have_required_fields(self, mappings: dict) -> None:
        missing: list[str] = []
        for key, entry in mappings.items():
            if not isinstance(entry, dict):
                missing.append(f"{key}: entry is not a dict")
                continue
            for field in self.REQUIRED_FIELDS:
                if field not in entry:
                    missing.append(f"{key}: missing '{field}'")
        assert not missing, "\n".join(missing)

    def test_all_mappings_have_model_identifier(self, mappings: dict) -> None:
        """Each mapping must have model_id or hf_id (some use HuggingFace IDs)."""
        errors: list[str] = []
        for key, entry in mappings.items():
            has_id = any(f in entry for f in self.IDENTIFIER_FIELDS)
            if not has_id:
                errors.append(f"{key}: must have 'model_id' or 'hf_id'")
        assert not errors, "\n".join(errors)

    def test_flare_name_follows_namespace_convention(self, mappings: dict) -> None:
        errors: list[str] = []
        for key, entry in mappings.items():
            name = entry.get("flare_name", "")
            if not name.startswith("pmoves/"):
                errors.append(f"{key}: flare_name '{name}' does not start with 'pmoves/'")
        assert not errors, "\n".join(errors)

    def test_providers_are_known(self, mappings: dict) -> None:
        unknown = []
        for key, entry in mappings.items():
            prov = entry.get("provider")
            if prov not in VALID_PROVIDERS:
                unknown.append(f"{key}: provider '{prov}'")
        assert not unknown, f"Unknown providers:\n" + "\n".join(unknown)

    def test_lanes_are_valid(self, mappings: dict) -> None:
        invalid = []
        for key, entry in mappings.items():
            lane = entry.get("lane")
            if lane not in VALID_LANES:
                invalid.append(f"{key}: lane '{lane}'")
        assert not invalid, f"Invalid lanes:\n" + "\n".join(invalid)

    def test_nodes_are_non_empty_lists(self, mappings: dict) -> None:
        errors: list[str] = []
        for key, entry in mappings.items():
            nodes = entry.get("nodes")
            if not isinstance(nodes, list) or len(nodes) == 0:
                errors.append(f"{key}: nodes must be a non-empty list")
        assert not errors, "\n".join(errors)

    def test_node_identifiers_are_known(self, mappings: dict) -> None:
        unknown = []
        for key, entry in mappings.items():
            for node in entry.get("nodes", []):
                if _norm_node(node) not in VALID_NODES:
                    unknown.append(f"{key}: node '{node}'")
        assert not unknown, f"Unknown nodes:\n" + "\n".join(unknown)

    def test_model_identifiers_are_non_empty_strings(self, mappings: dict) -> None:
        errors: list[str] = []
        for key, entry in mappings.items():
            for field in self.IDENTIFIER_FIELDS:
                if field in entry:
                    val = entry[field]
                    if not isinstance(val, str) or not val.strip():
                        errors.append(f"{key}: {field} must be a non-empty string")
        assert not errors, "\n".join(errors)


# ---------------------------------------------------------------------------
# Optional field sanity checks
# ---------------------------------------------------------------------------

class TestOptionalFields:
    def test_fallback_is_non_empty_string(self, mappings: dict) -> None:
        """Fallback references a model identifier string, not a mapping key."""
        for key, entry in mappings.items():
            fb = entry.get("fallback")
            if fb is not None:
                assert isinstance(fb, str) and fb.strip(), (
                    f"{key}: fallback must be a non-empty string"
                )

    def test_tensorzero_variants_are_strings(self, mappings: dict) -> None:
        errors: list[str] = []
        for key, entry in mappings.items():
            tz = entry.get("tensorzero_variant")
            if tz is not None and (not isinstance(tz, str) or not tz.strip()):
                errors.append(f"{key}: tensorzero_variant must be a non-empty string")
        assert not errors, "\n".join(errors)

    def test_claude_code_mappings_are_dicts(self, mappings: dict) -> None:
        for key, entry in mappings.items():
            ccm = entry.get("claude_code_mapping")
            if ccm is not None:
                assert isinstance(ccm, dict), f"{key}: claude_code_mapping must be a dict"

    def test_use_case_is_list_of_strings(self, mappings: dict) -> None:
        for key, entry in mappings.items():
            uc = entry.get("use_case")
            if uc is not None:
                assert isinstance(uc, list), f"{key}: use_case must be a list"
                for item in uc:
                    assert isinstance(item, str), f"{key}: use_case items must be strings"

    def test_vllm_compatible_is_bool(self, mappings: dict) -> None:
        for key, entry in mappings.items():
            vc = entry.get("vllm_compatible")
            if vc is not None:
                assert isinstance(vc, bool), f"{key}: vllm_compatible must be bool"

    def test_runtime_model_flag_is_bool(self, mappings: dict) -> None:
        for key, entry in mappings.items():
            rm = entry.get("runtime_model")
            if rm is not None:
                assert isinstance(rm, bool), f"{key}: runtime_model must be bool"


# ---------------------------------------------------------------------------
# Cross-mapping integrity
# ---------------------------------------------------------------------------

class TestCrossMappingIntegrity:
    def test_flare_names_are_valid_format(self, mappings: dict) -> None:
        """Every flare_name must be unique per lane.

        Coding plan entries intentionally alias cloud models (e.g. glm-coding
        and glm-5-1 both map to pmoves/glm-5.1), so we only enforce uniqueness
        within the same lane.
        """
        seen: dict[str, str] = {}  # flare_name+lane -> key
        dupes: list[str] = []
        for key, entry in mappings.items():
            name = entry.get("flare_name", "")
            lane = entry.get("lane", "")
            combo = f"{name}@{lane}"
            if combo in seen:
                dupes.append(f"{combo} (keys: {seen[combo]}, {key})")
            else:
                seen[combo] = key
        assert not dupes, f"Duplicate flare_name within same lane:\n" + "\n".join(dupes)

    def test_no_duplicate_provider_model_lane(self, mappings: dict) -> None:
        """Same provider+model_id+lane should not appear twice.

        Cross-lane duplicates are allowed (coding_plan aliases a cloud model).
        """
        seen: dict[str, str] = {}
        dupes: list[str] = []
        for key, entry in mappings.items():
            model = entry.get("model_id") or entry.get("hf_id", "")
            combo = f"{entry.get('provider')}:{model}:{entry.get('lane')}"
            if combo in seen:
                dupes.append(f"{combo} (keys: {seen[combo]}, {key})")
            else:
                seen[combo] = key
        assert not dupes, f"Duplicate provider+model+lane:\n" + "\n".join(dupes)

    def test_at_least_one_coding_lane_exists(self, mappings: dict) -> None:
        coding = [k for k, v in mappings.items() if v.get("lane") == "coding_plan"]
        assert len(coding) > 0, "Expected at least one coding_plan lane mapping"

    def test_at_least_one_cloud_lane_exists(self, mappings: dict) -> None:
        cloud = [k for k, v in mappings.items() if v.get("lane") == "cloud"]
        assert len(cloud) > 0, "Expected at least one cloud lane mapping"

    def test_at_least_one_local_lane_exists(self, mappings: dict) -> None:
        local = [k for k, v in mappings.items() if v.get("lane") == "local"]
        assert len(local) > 0, "Expected at least one local lane mapping"
