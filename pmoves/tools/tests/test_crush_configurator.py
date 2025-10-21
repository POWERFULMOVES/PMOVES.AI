"""Tests for Crush configurator utilities."""

import importlib.util
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "pmoves" / "tools" / "crush_configurator.py"

spec = importlib.util.spec_from_file_location("pmoves.tools.crush_configurator", MODULE_PATH)
assert spec and spec.loader, "unable to load crush_configurator module"
crush_configurator = importlib.util.module_from_spec(spec)
sys.modules.setdefault(spec.name, crush_configurator)
spec.loader.exec_module(crush_configurator)  # type: ignore[attr-defined]


def test_context_paths_exist():
    config, _ = crush_configurator.build_config()
    context_paths = config["options"]["context_paths"]

    assert context_paths, "expected at least one context path in the configuration"

    repo_root = crush_configurator.PROJECT_ROOT.parent
    missing = [
        candidate
        for candidate in context_paths
        if not (repo_root / Path(candidate)).exists()
    ]

    assert not missing, f"missing context paths: {missing}"
