import importlib
import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[4]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

sys.modules.setdefault("services", importlib.import_module("pmoves.services"))

from services.common.model_nexus import (
    NexusConfigError,
    get_nexus_lane,
    get_nexus_provider,
    load_model_nexus,
    model_nexus_path,
    provider_allowed_for_lane,
    provider_requires_nexus_adapter,
)


def test_load_model_nexus_default_path():
    data = load_model_nexus()
    assert data["contract_version"] == 1
    assert model_nexus_path().name == "model_nexus.yaml"


def test_get_nexus_provider_openai():
    provider = get_nexus_provider("openai")
    assert provider["sdk_family"] == "openai"
    assert provider["fallback_lane"] == "tensorzero"
    assert provider_requires_nexus_adapter("openai") is True


def test_get_nexus_provider_nvidia_nim():
    provider = get_nexus_provider("nvidia_nim")
    assert provider["sdk_family"] == "openai_compatible"
    assert provider["fallback_lane"] == "tensorzero"
    assert provider_requires_nexus_adapter("nvidia_nim") is False


def test_provider_allowed_for_lane_uses_default_and_overrides():
    assert provider_allowed_for_lane("coding_agents", "tensorzero") is True
    assert provider_allowed_for_lane("coding_agents", "openai") is True
    assert provider_allowed_for_lane("coding_agents", "nvidia_nim") is True
    assert provider_allowed_for_lane("nemotron_claw", "nvidia_nim") is True
    assert provider_allowed_for_lane("p7_and_skills", "anthropic") is False


def test_get_nexus_lane_missing_raises_key_error():
    with pytest.raises(KeyError):
        get_nexus_lane("missing-lane")


def test_load_model_nexus_missing_path_raises():
    missing = repo_root / "pmoves" / "config" / "does_not_exist.yaml"
    with pytest.raises(NexusConfigError):
        load_model_nexus(missing)
