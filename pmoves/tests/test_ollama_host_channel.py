"""ollama_host_channel.sh install gate: refuses before touching the host.

These paths need no Docker, network or root: each refusal happens before the
installer would run. The canary itself (Docker + GPU) is exercised by hand on a
node; its PASS/REFUSE report is what install reads, and that is faked here.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from pmoves.tools.bash_resolver import resolve_bash  # never System32's WSL stub

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "pmoves" / "tools" / "ollama_host_channel.sh"


def _install(state: Path, version: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "OLLAMA_CHANNEL_STATE": str(state), "OLLAMA_CHANNEL_VERSION": version}
    return subprocess.run([resolve_bash(), str(TOOL), "install"], env=env,
                          capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("bad", ["0.40.5;id", "0.40.5 && id", "$(id)", "-v", "../0.40.5", "latest"])
def test_install_rejects_anything_that_is_not_a_version(tmp_path, bad):
    r = _install(tmp_path, bad)
    assert r.returncode == 2 and "rejected" in r.stderr
    assert "uid=" not in r.stdout + r.stderr


def test_install_refuses_without_a_canary(tmp_path):
    r = _install(tmp_path, "0.41.0")
    assert r.returncode == 3 and "no canary for 0.41.0" in r.stderr


def test_install_refuses_a_refused_canary(tmp_path):
    (tmp_path / "canary-0.40.5.json").write_text(json.dumps({"verdict": "REFUSE"}))
    r = _install(tmp_path, "v0.40.5")  # leading v is accepted and stripped
    assert r.returncode == 3 and "did not PASS" in r.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="the root check is what is under test")
def test_install_needs_root_even_after_a_pass(tmp_path):
    (tmp_path / "canary-0.40.5.json").write_text(json.dumps({"verdict": "PASS"}))
    r = _install(tmp_path, "0.40.5")
    assert r.returncode == 3 and "needs root" in r.stderr


def test_make_passes_version_through_the_environment_not_the_recipe():
    text = (REPO_ROOT / "pmoves" / "Makefile").read_text(encoding="utf-8")
    for target in ("ollama-host-canary", "ollama-host-install"):
        assert f"{target}: export OLLAMA_CHANNEL_VERSION = $(VERSION)" in text
    assert "ollama_host_channel.sh canary $(VERSION)" not in text
    assert "ollama_host_channel.sh install $(VERSION)" not in text


def _rollback_with_fake_systemctl(tmp_path, environment: str, env_files: str = ""):
    """Run 'rollback' (print-only) with a stub systemctl answering 'show'."""
    bindir = tmp_path / "bin"; bindir.mkdir()
    stub = bindir / "systemctl"
    stub.write_text(
        "#!/bin/sh\n"
        'case "$*" in *EnvironmentFiles*) printf \'%s\\n\' "$FAKE_ENVFILES";;\n'
        '  *Environment*) printf \'%s\\n\' "$FAKE_ENV";; esac\n')
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "FAKE_ENV": environment,
           "FAKE_ENVFILES": env_files, "OLLAMA_CHANNEL_STATE": str(tmp_path / "state")}
    env.pop("OLLAMA_CHANNEL_MODELS", None)
    return subprocess.run([resolve_bash(), str(TOOL), "rollback"], env=env,
                          capture_output=True, text=True, timeout=30)


def test_store_found_when_ollama_models_is_the_first_environment_entry(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    r = _rollback_with_fake_systemctl(tmp_path, f"OLLAMA_MODELS={store} OLLAMA_HOST=0.0.0.0")
    assert r.returncode == 0 and f"-C {store} " in r.stdout


def test_store_found_in_an_environment_file(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    envfile = tmp_path / "ollama-service-environment"
    envfile.write_text(f'export OLLAMA_MODELS="{store}"\n')
    r = _rollback_with_fake_systemctl(tmp_path, "OLLAMA_HOST=0.0.0.0", f"{envfile} (ignore_errors=no)")
    assert r.returncode == 0 and f"-C {store} " in r.stdout


def test_missing_store_is_refused_not_guessed(tmp_path):
    r = _rollback_with_fake_systemctl(tmp_path, f"OLLAMA_MODELS={tmp_path / 'gone'}")
    assert r.returncode != 0 and "model store not found" in r.stderr


def test_rollback_removes_everything_a_migration_creates(tmp_path):
    store = tmp_path / "store"; store.mkdir()
    r = _rollback_with_fake_systemctl(tmp_path, f"OLLAMA_MODELS={store}")
    assert f"{store}/manifests-v2 {store}/metadata -delete" in r.stdout
    assert "OLLAMA_NOPRUNE=1" in r.stdout
