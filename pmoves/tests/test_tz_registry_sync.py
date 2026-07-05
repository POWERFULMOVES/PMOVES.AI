"""tz_registry_sync: splice registry-generated model blocks into tensorzero.toml."""
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.tz_registry_sync import sync_registry_section  # noqa: E402

STATIC = """
[models.chat_static]
routing = ["p"]

[models.chat_static.providers.p]
type = "openai"
api_base = "https://example.com/v1"
model_name = "m"
api_key_location = "none"

# BEGIN REGISTRY-MANAGED MODELS (generated - do not hand-edit)
[models.registry_worker_glm]
routing = ["bootstrap_parent"]

[models.registry_worker_glm.providers.bootstrap_parent]
type = "openai"
api_base = "https://old.example/v1"
model_name = "old"
api_key_location = "none"
# END REGISTRY-MANAGED MODELS

[functions.f]
type = "chat"
"""

REGISTRY = """
[models.registry_worker_glm]
routing = ["ollama_local"]

[models.registry_worker_glm.providers.ollama_local]
type = "openai"
api_base = "http://pmoves-ollama:11434/v1"
model_name = "selected-by-registry"
api_key_location = "none"

[models.not_registry_prefixed]
routing = ["x"]
"""


def test_replaces_marker_section_with_registry_models():
    out = sync_registry_section(STATIC, REGISTRY)
    parsed = tomllib.loads(out)
    glm = parsed["models"]["registry_worker_glm"]["providers"]["ollama_local"]
    assert glm["model_name"] == "selected-by-registry"
    assert "chat_static" in parsed["models"]          # outside markers untouched
    assert "not_registry_prefixed" not in parsed["models"]  # only registry_* spliced
    assert "f" in parsed["functions"]


def test_idempotent():
    once = sync_registry_section(STATIC, REGISTRY)
    twice = sync_registry_section(once, REGISTRY)
    assert once == twice


def test_missing_markers_raises():
    with pytest.raises(ValueError):
        sync_registry_section("[models.x]\nrouting = []\n", REGISTRY)


def test_synthesize_lane_blocks_from_models_payload():
    import tomllib as _toml
    from tools.tz_registry_sync import synthesize_lane_blocks
    payload = {"items": [
        {"model_id": "some-model:tag",
         "api_base": "http://backend:1234/v1",
         "aliases": [{"alias": "registry_worker_x", "context": "c"},
                     {"alias": "friendly-name", "context": "c"}]},
        {"model_id": "no-lane-model", "aliases": []},
    ]}
    body = synthesize_lane_blocks(payload)
    parsed = _toml.loads(body)
    lane = parsed["models"]["registry_worker_x"]["providers"]["local_active"]
    assert lane["model_name"] == "some-model:tag"
    assert lane["api_base"] == "http://backend:1234/v1"
    assert "friendly-name" not in parsed["models"]   # only registry_* synthesized
    assert len(parsed["models"]) == 1


def test_merge_preserves_lanes_absent_from_registry():
    import tomllib as _toml
    static = """
# BEGIN REGISTRY-MANAGED MODELS
[models.registry_worker_a]
routing = ["bootstrap_parent"]

[models.registry_worker_a.providers.bootstrap_parent]
type = "openai"
api_base = "https://cloud.example/v1"
model_name = "cloud-parent-a"
api_key_location = "none"

[models.registry_worker_b]
routing = ["bootstrap_parent"]

[models.registry_worker_b.providers.bootstrap_parent]
type = "openai"
api_base = "https://cloud.example/v1"
model_name = "cloud-parent-b"
api_key_location = "none"
# END REGISTRY-MANAGED MODELS
"""
    registry = """
[models.registry_worker_a]
routing = ["local_active"]

[models.registry_worker_a.providers.local_active]
type = "openai"
api_base = "http://local:1/v1"
model_name = "local-a"
api_key_location = "none"
"""
    out = sync_registry_section(static, registry)
    parsed = _toml.loads(out)
    assert parsed["models"]["registry_worker_a"]["providers"]["local_active"]["model_name"] == "local-a"
    assert parsed["models"]["registry_worker_b"]["providers"]["bootstrap_parent"]["model_name"] == "cloud-parent-b"


def test_default_sync_fetches_alias_lanes_from_api_models(monkeypatch, tmp_path, capsys):
    """The default sync (no --models-json) must fetch /api/models — the only
    endpoint carrying registry_* aliases — so a promoted lane gets its real
    body while lanes absent from the payload keep their bootstrap block."""
    import io
    import json as _json
    import tomllib as _toml

    import tools.tz_registry_sync as tz

    static = """
# BEGIN REGISTRY-MANAGED MODELS
[models.registry_worker_qwen]
routing = ["bootstrap_parent"]

[models.registry_worker_qwen.providers.bootstrap_parent]
type = "openai"
api_base = "https://cloud.example/v1"
model_name = "cloud-parent-qwen"
api_key_location = "none"

[models.registry_worker_other]
routing = ["bootstrap_parent"]

[models.registry_worker_other.providers.bootstrap_parent]
type = "openai"
api_base = "https://cloud.example/v1"
model_name = "cloud-parent-other"
api_key_location = "none"
# END REGISTRY-MANAGED MODELS
"""
    toml_path = tmp_path / "tensorzero.toml"
    toml_path.write_text(static, encoding="utf-8")
    monkeypatch.setattr(tz, "TZ_TOML", toml_path)

    # registry_worker_qwen is promoted (local alias + api_base); the "other"
    # lane is absent from /api/models and must fall through to the guard.
    payload = {"items": [
        {"model_id": "qwen3-coder:30b",
         "api_base": "http://pmoves-ollama:11434/v1",
         "aliases": [{"alias": "registry_worker_qwen", "context": "worker"}]},
    ]}

    requested = {}

    def fake_urlopen(url, timeout=None):
        requested["url"] = url
        return io.BytesIO(_json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(tz.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(sys, "argv", ["tz_registry_sync.py", "--dry-run"])

    assert tz.main() == 0
    assert requested["url"].endswith("/api/models"), requested["url"]

    parsed = _toml.loads(capsys.readouterr().out)
    # promoted lane got its real registry-managed body from /api/models
    qwen = parsed["models"]["registry_worker_qwen"]["providers"]["local_active"]
    assert qwen["model_name"] == "qwen3-coder:30b"
    assert qwen["api_base"] == "http://pmoves-ollama:11434/v1"
    # lane absent from the payload keeps its bootstrap block (#1950 guard)
    other = parsed["models"]["registry_worker_other"]["providers"]["bootstrap_parent"]
    assert other["model_name"] == "cloud-parent-other"
