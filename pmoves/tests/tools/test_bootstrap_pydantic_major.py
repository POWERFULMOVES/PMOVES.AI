"""env-bootstrap-check must refuse pydantic v1, not just a missing pydantic.

The funnel imports v2-only API (ConfigDict, field_validator) from
secret_shape_rules. A v1 install imports cleanly, so an import-only probe
passed it and the funnel then died mid-run. The fake interpreters below run
the REAL probe code against a fabricated pydantic distribution.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from tools.bootstrap_light_env import _precheck_only


def _fake_venv(tmp_path: Path, version: str) -> Path:
    site = tmp_path / f"site-{version}"
    (site / "pydantic").mkdir(parents=True)
    (site / "pydantic" / "__init__.py").write_text(f"VERSION = {version!r}\n")
    dist = site / f"pydantic-{version}.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(f"Metadata-Version: 2.1\nName: pydantic\nVersion: {version}\n")
    venv = tmp_path / f"venv-{version}"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    # -S: no site-packages, so only the fabricated distribution is visible.
    python.write_text(f'#!/bin/sh\nPYTHONPATH="{site}" exec "{sys.executable}" -S "$@"\n')
    python.chmod(python.stat().st_mode | stat.S_IEXEC)
    return venv


def _reqs(tmp_path: Path) -> Path:
    req = tmp_path / "requirements-lite.txt"
    req.write_text("pydantic>=2\n")
    return req


def test_pydantic_v1_fails_the_precheck_with_exit_3(tmp_path, capsys):
    assert _precheck_only(_fake_venv(tmp_path, "1.10.13"), [_reqs(tmp_path)]) == 3
    assert "major version < 2" in capsys.readouterr().err


def test_pydantic_v2_passes_the_precheck(tmp_path):
    """Positive control: same harness, only the version differs."""
    assert _precheck_only(_fake_venv(tmp_path, "2.12.5"), [_reqs(tmp_path)]) == 0
