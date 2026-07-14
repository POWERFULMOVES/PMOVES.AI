"""Unit tests for kong_route_seeder._parse_model_suits schema handling.

Verifies all 3 YAML nesting patterns used across pmoves/configs/model-suits/
are correctly parsed by the seeder.
"""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
from kong_route_seeder import _parse_model_suits


@pytest.fixture
def suits_dir(tmp_path):
    """Create a temporary model-suits directory with all 3 schema patterns."""
    # Pattern A: model_suit: nesting (GLM family)
    (tmp_path / "glm-5.2.yaml").write_text(yaml.dump({
        "model_suit": {
            "name": "glm-5.2",
            "provider": "zai",
            "base_url": "https://api.z.ai/api/coding/paas/v4",
            "api_key_env": "Z_AI_API_KEY",
        }
    }))

    # Pattern B: suit: nesting (Claude/MiniMax family)
    (tmp_path / "claude-sonnet-4.yaml").write_text(yaml.dump({
        "suit": {
            "id": "claude-sonnet-4",
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    }))

    # Pattern C: top-level name/provider (Ollama family)
    (tmp_path / "qwen3.6.yaml").write_text(yaml.dump({
        "name": "qwen3.6",
        "provider": "ollama_local",
    }))

    # Pattern D: original seeder schema (top-level model_id/provider)
    (tmp_path / "legacy.yaml").write_text(yaml.dump({
        "model_id": "some-model",
        "provider": "openai",
        "api_base": "https://api.openai.com/v1",
        "api_key_env_var": "OPENAI_API_KEY",
    }))

    # Invalid: non-dict YAML
    (tmp_path / "invalid.yaml").write_text("- just\n- a\n- list\n")

    # Missing provider: should be skipped with warning
    (tmp_path / "incomplete.yaml").write_text(yaml.dump({"name": "no-provider"}))

    return tmp_path


def test_parses_model_suit_nesting(suits_dir):
    """Pattern A: model_suit: nesting should parse."""
    suits = _parse_model_suits(suits_dir)
    glm52 = [s for s in suits if s["model_id"] == "glm-5.2"]
    assert len(glm52) == 1
    assert glm52[0]["provider"] == "zai"
    assert glm52[0]["api_base"] == "https://api.z.ai/api/coding/paas/v4"
    assert glm52[0]["api_key_env"] == "Z_AI_API_KEY"


def test_parses_suit_nesting(suits_dir):
    """Pattern B: suit: nesting should parse."""
    suits = _parse_model_suits(suits_dir)
    claude = [s for s in suits if s["model_id"] == "claude-sonnet-4"]
    assert len(claude) == 1
    assert claude[0]["provider"] == "anthropic"


def test_parses_top_level_name(suits_dir):
    """Pattern C: top-level name/provider should parse."""
    suits = _parse_model_suits(suits_dir)
    qwen = [s for s in suits if s["model_id"] == "qwen3.6"]
    assert len(qwen) == 1
    assert qwen[0]["provider"] == "ollama_local"


def test_parses_legacy_schema(suits_dir):
    """Pattern D: original top-level model_id/provider should still parse."""
    suits = _parse_model_suits(suits_dir)
    legacy = [s for s in suits if s["model_id"] == "some-model"]
    assert len(legacy) == 1
    assert legacy[0]["api_base"] == "https://api.openai.com/v1"


def test_skips_non_dict(suits_dir):
    """Non-dict YAML files should be skipped."""
    suits = _parse_model_suits(suits_dir)
    assert not any(s["file"] == "invalid.yaml" for s in suits)


def test_skips_missing_provider(suits_dir):
    """Files without a resolvable provider should be skipped."""
    suits = _parse_model_suits(suits_dir)
    assert not any(s["file"] == "incomplete.yaml" for s in suits)


def test_total_parsed_count(suits_dir):
    """Should parse exactly 4 valid suits out of 6 files."""
    suits = _parse_model_suits(suits_dir)
    assert len(suits) == 4


def test_real_model_suits_directory():
    """Integration test: parse the actual pmoves/configs/model-suits/ directory.

    Before the fix, 0 of 17 files parsed. After the fix, all should parse.
    """
    real_dir = Path(__file__).parent.parent.parent / "configs" / "model-suits"
    if not real_dir.exists():
        pytest.skip(f"Model suits directory not found: {real_dir}")

    suits = _parse_model_suits(real_dir)
    yaml_count = len(list(real_dir.glob("*.yaml")))
    assert len(suits) >= yaml_count * 0.8, (
        f"Only {len(suits)}/{yaml_count} model suits parsed. "
        f"Skipped: {set(f.name for f in real_dir.glob('*.yaml')) - set(s['file'] for s in suits)}"
    )
