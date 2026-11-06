"""Registry-pinned host-leak guards are ENFORCED, not just declared.

bootstrap/registry.json declares SSL_CERT_FILE, *_CA_BUNDLE, *_PROXY etc.
"Always empty" in env.shared so a Windows host path never reaches a Linux
container. Nothing applied that after first bootstrap: measured on Z890
2026-11-06, env.shared carried a miniconda SSL_CERT_FILE from an install since
removed, and every claude-pmoves session exported a CA file that does not
exist. `--enforce-pinned` (run by `make env-shared-repair`) resets the drift.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MOD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_env.py"
_spec = importlib.util.spec_from_file_location("bootstrap_env_pinned_under_test", _MOD_PATH)
be = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = be
_spec.loader.exec_module(be)

REAL_REGISTRY = Path(__file__).resolve().parents[1] / "bootstrap" / "registry.json"
SHARED = "pmoves/" + "env." + "shared"
LEAK_GUARDS = {
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
}


def _registry(**pins: str) -> dict:
    return {"version": 1, "services": [{"id": "shared", "variables": [
        {"key": k, "file": SHARED, "default": v, "pinned": True} for k, v in pins.items()
    ] + [{"key": "FREE", "file": SHARED, "default": ""}]}]}


def _env(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "env.shared"
    p.write_text(text, encoding="utf-8")
    return p


def test_a_drifted_pin_is_reset_and_nothing_else_moves(tmp_path):
    env = _env(tmp_path, "# hdr\nA=1\nSSL_CERT_FILE=C:\\gone\\conda\\cacert.crt\nFREE=keep-me\nB=2\n")
    drifted = be.enforce_pinned(_registry(SSL_CERT_FILE=""), env_path=env)
    assert drifted == ["SSL_CERT_FILE"]
    assert env.read_text(encoding="utf-8") == "# hdr\nA=1\nSSL_CERT_FILE=\nFREE=keep-me\nB=2\n"


def test_unpinned_keys_are_never_touched(tmp_path):
    env = _env(tmp_path, "FREE=host-value\n")
    assert be.enforce_pinned(_registry(SSL_CERT_FILE=""), env_path=env) == []
    assert env.read_text(encoding="utf-8") == "FREE=host-value\n"


@pytest.mark.parametrize("text", ["SSL_CERT_FILE=\n", 'SSL_CERT_FILE=""\n', "SSL_CERT_FILE=''\n", "OTHER=1\n"])
def test_at_default_or_absent_is_not_drift_and_writes_nothing(tmp_path, text):
    env = _env(tmp_path, text)
    assert be.enforce_pinned(_registry(SSL_CERT_FILE=""), env_path=env) == []
    assert env.read_text(encoding="utf-8") == text


def test_a_later_duplicate_is_what_counts_and_is_dropped(tmp_path):
    # Last-wins parsers read the second line; the reset must not leave it.
    env = _env(tmp_path, "SSL_CERT_FILE=\nX=1\nSSL_CERT_FILE=/host/path\n")
    assert be.enforce_pinned(_registry(SSL_CERT_FILE=""), env_path=env) == ["SSL_CERT_FILE"]
    assert env.read_text(encoding="utf-8") == "SSL_CERT_FILE=\nX=1\n"


def test_check_mode_reports_without_writing(tmp_path):
    env = _env(tmp_path, "HTTPS_PROXY=http://user:pw@proxy:3128\n")
    before = env.read_text(encoding="utf-8")
    assert be.enforce_pinned(_registry(HTTPS_PROXY=""), env_path=env, dry_run=True) == ["HTTPS_PROXY"]
    assert env.read_text(encoding="utf-8") == before


def test_a_pin_outside_env_shared_is_a_registry_error(tmp_path):
    reg = {"services": [{"id": "x", "variables": [
        {"key": "K", "file": "pmoves/env.tier-agent", "default": "", "pinned": True}]}]}
    with pytest.raises(ValueError, match="only"):
        be.enforce_pinned(reg, env_path=_env(tmp_path, "K=v\n"))


def test_cli_prints_names_not_values(tmp_path, monkeypatch, capsys):
    env = _env(tmp_path, "HTTPS_PROXY=http://user:s3cretpw@proxy:3128\n")
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(_registry(HTTPS_PROXY="")), encoding="utf-8")
    monkeypatch.setattr(be, "ENV_SHARED_PATH", env)
    assert be.main(["--registry", str(reg), "--enforce-pinned-check"]) == 1
    assert be.main(["--registry", str(reg), "--enforce-pinned"]) == 0
    out = capsys.readouterr()
    assert "HTTPS_PROXY" in out.out + out.err
    assert "s3cretpw" not in out.out + out.err
    assert be.main(["--registry", str(reg), "--enforce-pinned-check"]) == 0


def test_the_real_registry_pins_every_leak_guard_empty():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    pins = {v["key"]: v for v in be.pinned_variables(data)}
    assert LEAK_GUARDS <= set(pins), LEAK_GUARDS - set(pins)
    for k in LEAK_GUARDS:
        assert pins[k]["default"] == "" and pins[k]["file"] == SHARED


def test_the_funnel_runs_the_enforcement():
    mk = (Path(__file__).resolve().parents[1] / "mk" / "codex.mk").read_text(encoding="utf-8")
    repair = mk.split("\nenv-shared-repair:", 1)[1].split("\n\n", 1)[0]
    assert "bootstrap_env.py --enforce-pinned" in repair
    from_prod = mk.split("\nsecrets-funnel-from-prod:", 1)[1].split("\n\n", 1)[0]
    assert from_prod.index("FORCE=1") < from_prod.index("--enforce-pinned")
    funnel = mk.split("\nsecrets-funnel:", 1)[1].split("\n\n", 1)[0]
    assert "env-shared-repair" in funnel
