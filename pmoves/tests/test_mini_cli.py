from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

from typer.testing import CliRunner


def test_bootstrap_stages_bundle_and_updates_env(tmp_path) -> None:
    if "yaml" not in sys.modules:
        yaml_module = ModuleType("yaml")

        def _yaml_stub(*args, **kwargs):  # pragma: no cover - simple stub
            raise RuntimeError("yaml stub used without dependency")

        yaml_module.safe_load = _yaml_stub  # type: ignore[attr-defined]
        yaml_module.safe_dump = _yaml_stub  # type: ignore[attr-defined]
        sys.modules["yaml"] = yaml_module

    from pmoves.tools import mini_cli  # imported lazily to honour stub

    runner = CliRunner()
    registry = tmp_path / "registry.json"
    env_rel = Path("tmp/pytest-mini-cli/env.shared")
    registry.write_text(
        json.dumps(
            {
                "version": 1,
                "services": [
                    {
                        "id": "demo",
                        "name": "Demo",
                        "variables": [
                            {
                                "file": env_rel.as_posix(),
                                "key": "DEMO_TOKEN",
                                "required": True,
                                "default": "demo-value",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    destination = tmp_path / "bundle"
    result = runner.invoke(
        mini_cli.app,
        [
            "bootstrap",
            "--registry",
            str(registry),
            "--accept-defaults",
            "--output",
            str(destination),
        ],
    )
    assert result.exit_code == 0, result.output

    env_file = Path.cwd() / env_rel
    try:
        assert env_file.exists()
        content = env_file.read_text(encoding="utf-8")
        assert "DEMO_TOKEN=demo-value" in content
    finally:
        shutil.rmtree(env_file.parent, ignore_errors=True)

    wizard = destination / "scripts" / "install" / "wizard.sh"
    assert wizard.exists()
    source_wizard = mini_cli.PROVISIONING_BUNDLE_FILES[Path("scripts/install/wizard.sh")]
    assert (wizard.stat().st_mode & 0o777) == (source_wizard.stat().st_mode & 0o777)


def test_deps_check_reports_missing(monkeypatch) -> None:
    from pmoves.tools import mini_cli

    runner = CliRunner()
    monkeypatch.setattr(mini_cli, "_command_available", lambda command: command == "pytest")

    result = runner.invoke(mini_cli.app, ["deps", "check"])
    assert result.exit_code == 1
    assert "make: missing" in result.output
    assert "jq: missing" in result.output
    assert "pytest: available" in result.output


def test_deps_install_container_requires_docker(monkeypatch) -> None:
    from pmoves.tools import mini_cli

    runner = CliRunner()
    monkeypatch.setattr(mini_cli, "_command_available", lambda command: False)
    monkeypatch.setattr(mini_cli, "_docker_available", lambda: False)

    result = runner.invoke(mini_cli.app, ["deps", "install", "--use-container"])
    assert result.exit_code == 1
    assert "Docker CLI is required" in result.output
