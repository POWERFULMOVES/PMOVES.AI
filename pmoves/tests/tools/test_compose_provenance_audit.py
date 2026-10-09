"""compose_provenance_audit — classification + ratchet tests.

The tool classifies every compose build: stanza and fails on unregistered
superproject shims. These tests pin the classifier on synthetic compose
documents and the ratchet behavior (unregistered -> exit 1, registered ->
exit 0, stale baseline entry -> exit 1).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import compose_provenance_audit as cpa  # noqa: E402

PY = sys.executable
TOOL = TOOLS / "compose_provenance_audit.py"


def _svc(context):
    return {"services": {"x": {"build": {"context": context}}}}


class TestClassification:
    def test_submodule_context(self):
        assert cpa._classify({"context": "../PMOVES-Archon"}) == cpa.SUBMODULE
        assert cpa._classify({"context": "./PMOVES-ToKenism-Multi/pmoves-nextjs"}) == cpa.SUBMODULE
        assert cpa._classify({"context": "../PMOVES.YT"}) == cpa.SUBMODULE

    def test_superproject_shim(self):
        assert cpa._classify({"context": "."}) == cpa.SHIM
        assert cpa._classify({"context": "./services"}) == cpa.SHIM
        assert cpa._classify({"context": ".."}) == cpa.SHIM
        assert cpa._classify(".") == cpa.SHIM

    def test_string_form(self):
        assert cpa._classify("../PMOVES-OpenRoom") == cpa.SUBMODULE
        assert cpa._classify(".") == cpa.SHIM


class TestComposeSpecTags:
    def test_reset_override_tags_parse(self, tmp_path, monkeypatch):
        compose = tmp_path / "docker-compose.yml"
        compose.write_text(
            "services:\n"
            "  shim-svc:\n"
            "    build:\n"
            "      context: .\n"
            "    devices: !reset []\n"
            "volumes:\n"
            "  data:\n"
            "    driver: !reset null\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(cpa, "PMOVES_DIR", tmp_path)
        monkeypatch.setattr(cpa, "BASELINE", tmp_path / "baseline.json")
        found = cpa.collect()
        assert found["shim-svc"]["class"] == cpa.SHIM


class TestRatchetBehavior:
    def _run(self, baseline_services):
        return subprocess.run(
            [PY, str(TOOL)], capture_output=True, text=True,
            env={**__import__("os").environ},
            cwd=str(TOOLS.parent),
        )

    def test_fails_on_unregistered_shim(self, tmp_path, monkeypatch):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  rogue:\n    build:\n      context: .\n", encoding="utf-8")
        (tmp_path / "baseline.json").write_text(json.dumps({"shims": []}), encoding="utf-8")
        import importlib
        importlib.reload(cpa)
        monkeypatch.setattr(cpa, "PMOVES_DIR", tmp_path)
        monkeypatch.setattr(cpa, "BASELINE", tmp_path / "baseline.json")
        # exit code path is exercised via main(); call directly with argv patched
        monkeypatch.setattr(sys, "argv", ["compose_provenance_audit.py"])
        assert cpa.main() == 1

    def test_passes_when_registered(self, tmp_path, monkeypatch):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  known:\n    build:\n      context: .\n", encoding="utf-8")
        (tmp_path / "baseline.json").write_text(json.dumps({"shims": ["known"]}), encoding="utf-8")
        import importlib
        importlib.reload(cpa)
        monkeypatch.setattr(cpa, "PMOVES_DIR", tmp_path)
        monkeypatch.setattr(cpa, "BASELINE", tmp_path / "baseline.json")
        monkeypatch.setattr(sys, "argv", ["compose_provenance_audit.py"])
        assert cpa.main() == 0

    def test_fails_on_stale_baseline_entry(self, tmp_path, monkeypatch):
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  known:\n    build:\n      context: ../PMOVES-OpenRoom\n", encoding="utf-8")
        (tmp_path / "baseline.json").write_text(json.dumps({"shims": ["known"]}), encoding="utf-8")
        import importlib
        importlib.reload(cpa)
        monkeypatch.setattr(cpa, "PMOVES_DIR", tmp_path)
        monkeypatch.setattr(cpa, "BASELINE", tmp_path / "baseline.json")
        monkeypatch.setattr(sys, "argv", ["compose_provenance_audit.py"])
        assert cpa.main() == 1


class TestRemoteForkConsumer:
    def test_detects_in_image_clone(self):
        df = (
            "FROM python:3.11\n"
            "RUN git clone --depth=1 https://github.com/POWERFULMOVES/PMOVES-Widget.git /app\n"
        )
        assert cpa._clone_fork_repo(df) == "PMOVES-Widget"

    def test_detects_cache_bust_ref_url(self):
        df = "ADD https://api.github.com/repos/POWERFULMOVES/PMOVES-Agent-Zero/git/ref/heads/main /tmp/ref.json\n"
        assert cpa._clone_fork_repo(df) == "PMOVES-Agent-Zero"

    def test_no_clone_is_none(self):
        assert cpa._clone_fork_repo("FROM alpine\nRUN echo hi") is None

    def test_env_var_context_classifies_submodule(self):
        assert cpa._classify({"context": "${INTEGRATIONS_WORKSPACE:-../integrations-workspace}/PMOVES-Agent-Zero"}) == cpa.SUBMODULE
