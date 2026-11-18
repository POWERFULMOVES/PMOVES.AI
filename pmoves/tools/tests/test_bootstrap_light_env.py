"""bootstrap_light_env.py heals a half-uninstalled venv instead of dying in it.

Measured on the 4090 (2026-11-17): every directory under an OneDrive-synced
`.venv-pmoves` carries FILE_ATTRIBUTE_READONLY (169 of 169), and Windows
refuses `rmdir` on such a directory with WinError 5. A `uv pip install` that
upgraded numpy deleted every file, failed on the first directory, and left two
`numpy-*.dist-info` with no RECORD. Every later install then failed, so
`env-bootstrap-lite` -- and the whole secrets funnel behind it -- could not
run. The `--check` gate passed anyway, because an empty `numpy/` imports as a
namespace package.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "bootstrap_light_env.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("bootstrap_light_env", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _site_packages(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Lib" / "site-packages"
    return venv / "lib" / "python3.11" / "site-packages"


def _fake_venv(root: Path) -> Path:
    venv = root / ".venv-pmoves"
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    py.parent.mkdir(parents=True)
    py.write_text("")
    _site_packages(venv).mkdir(parents=True)
    return venv


def _dist(venv: Path, name: str, *, record: bool) -> None:
    info = _site_packages(venv) / f"{name}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Name: x\n")
    if record:
        (info / "RECORD").write_text("")


def test_a_dist_without_record_is_reported(mod, tmp_path):
    venv = _fake_venv(tmp_path)
    _dist(venv, "pyyaml-6.0.2", record=True)
    _dist(venv, "numpy-2.2.6", record=False)
    _dist(venv, "numpy-2.4.5", record=False)

    assert mod.broken_distributions(venv) == ["numpy-2.2.6", "numpy-2.4.5"]


def test_a_healthy_venv_reports_nothing(mod, tmp_path):
    venv = _fake_venv(tmp_path)
    _dist(venv, "pyyaml-6.0.2", record=True)

    assert mod.broken_distributions(venv) == []


def test_precheck_fails_on_a_half_uninstalled_dist_even_when_imports_pass(
    mod, tmp_path, capsys
):
    # The import probe cannot see this: an empty package dir imports as a
    # namespace package. Integrity has to be read from the dist-info.
    venv = _fake_venv(tmp_path)
    _dist(venv, "numpy-2.4.5", record=False)
    reqs = tmp_path / "req.txt"
    reqs.write_text("")

    assert mod._precheck_only(venv, [reqs]) == 3
    err = capsys.readouterr().err
    assert "numpy-2.4.5" in err
    assert "env-bootstrap-lite" in err


def test_heal_moves_a_broken_venv_aside_and_ensure_venv_rebuilds(
    mod, tmp_path, monkeypatch
):
    venv = _fake_venv(tmp_path)
    _dist(venv, "numpy-2.4.5", record=False)
    created: list[list[str]] = []

    def fake_run(cmd):
        created.append(cmd)
        _fake_venv(tmp_path)  # what `uv venv` / `python -m venv` would leave

    monkeypatch.setattr(mod, "run", fake_run)
    monkeypatch.setattr(mod.shutil, "which", lambda name: "uv" if name == "uv" else None)

    _, py = mod.ensure_venv(venv)

    quarantined = [p for p in tmp_path.iterdir() if p.name.startswith(".venv-pmoves.broken-")]
    assert len(quarantined) == 1, "the broken venv is kept for inspection, not deleted"
    assert (quarantined[0] / "Lib" if os.name == "nt" else quarantined[0] / "lib").exists()
    assert created and created[0][:2] == ["uv", "venv"], "a fresh venv was created"
    assert py.exists()
    assert mod.broken_distributions(venv) == []


def test_ensure_venv_leaves_a_healthy_venv_alone(mod, tmp_path, monkeypatch):
    venv = _fake_venv(tmp_path)
    _dist(venv, "pyyaml-6.0.2", record=True)
    monkeypatch.setattr(mod, "run", lambda cmd: pytest.fail(f"unexpected {cmd}"))

    mod.ensure_venv(venv)

    assert not [p for p in tmp_path.iterdir() if ".broken-" in p.name]


@pytest.mark.skipif(os.name != "nt", reason="FILE_ATTRIBUTE_READONLY is Windows-only")
def test_readonly_directories_are_cleared_so_installers_can_remove_them(mod, tmp_path):
    venv = _fake_venv(tmp_path)
    pkg = _site_packages(venv) / "numpy"
    pkg.mkdir()
    subprocess.run(["attrib", "+R", str(pkg)], check=True)
    with pytest.raises(PermissionError):
        os.rmdir(pkg)  # the measured failure, reproduced

    cleared = mod.clear_readonly(venv)

    assert cleared >= 1
    assert not os.stat(pkg).st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
    os.rmdir(pkg)
