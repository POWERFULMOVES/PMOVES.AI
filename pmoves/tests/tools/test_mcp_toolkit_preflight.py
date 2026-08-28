"""Offline tests for the MCP Toolkit gateway preflight.

Docker is stubbed so these run on a runner with no daemon and on any arch; what
is under test is the verdict logic and — most importantly — that an
unmeasurable gateway exits 3 rather than 0.

Context: mcp-toolkit-gateway-listen.sh checked Docker and the profile, then
started a gateway. It never checked the SECRET RESOLVER. On 2026-08-28 the
resolver was wedged (`ResolverService/GetSecrets: deadline_exceeded`, surviving
a Docker Desktop restart) and the gateway started regardless, serving
`github-official` with an empty token. Every call returned 401, and nothing at
start time explained why.

Stubbing `_docker` rather than PATH follows docker_host_policy_check.py, and is
required on Windows besides: Git Bash resolves `docker` to `docker.exe` and
never sees an extensionless stub, so a PATH stub silently exercises the REAL
daemon — which is exactly how an earlier draft of this file "passed" against
live profiles instead of its fixture.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "pmoves" / "tools" / "mcp_toolkit_preflight.py"
LISTENER = REPO_ROOT / "pmoves" / "scripts" / "mcp-toolkit-gateway-listen.sh"

spec = importlib.util.spec_from_file_location("mcp_toolkit_preflight", MODULE)
assert spec and spec.loader
pf = importlib.util.module_from_spec(spec)
sys.modules["mcp_toolkit_preflight"] = pf
spec.loader.exec_module(pf)


PROFILE_LS = "ID\tName\ndefault\tDefault\npmoves_5090_web\tPMOVES-5090-web\n"
PROFILE_SHOW = """
version: 1
id: pmoves_5090_web
servers:
    - type: image
      snapshot:
        server:
            name: github-official
            secrets:
                - name: github.personal_access_token
                  env: GITHUB_PERSONAL_ACCESS_TOKEN
    - type: image
      snapshot:
        server:
            name: context7
"""
WEDGED = (
    'deadline_exceeded: Post "http://unix/resolver.v1.ResolverService/GetSecrets": '
    "net/http: timeout awaiting response headers"
)


def _fake_docker(monkeypatch, *, secrets, profiles: str = PROFILE_LS):
    def fake(*args: str, timeout: int = 45) -> str:
        joined = " ".join(args)
        if joined.startswith("mcp profile ls"):
            return profiles
        if joined.startswith("mcp secret ls"):
            if secrets is None:
                raise pf.Unmeasured("docker mcp secret ls failed: resolver down")
            return secrets
        if joined.startswith("mcp profile show"):
            return PROFILE_SHOW
        return ""

    monkeypatch.setattr(pf, "_docker", fake)


def test_a_healthy_gateway_passes(monkeypatch):
    _fake_docker(monkeypatch, secrets="NAME\ne2b.api_key\n")
    assert pf.main(["--profile", "pmoves_5090_web"]) == 0


def test_a_wedged_resolver_exits_1(monkeypatch):
    """A measured failure, distinct from an unmeasurable one."""
    _fake_docker(monkeypatch, secrets=WEDGED)
    assert pf.main(["--profile", "pmoves_5090_web"]) == 1


def test_a_wedged_resolver_names_the_servers_at_risk(monkeypatch, capsys):
    """A generic warning is not actionable; the operator needs the server list."""
    _fake_docker(monkeypatch, secrets=WEDGED)
    pf.main(["--profile", "pmoves_5090_web"])
    err = capsys.readouterr().err
    assert "github-official" in err, err
    assert "github.personal_access_token" in err, err


def test_a_server_with_no_secret_is_not_reported(monkeypatch):
    """context7 declares none, so it is not 'at risk' and must not be listed."""
    _fake_docker(monkeypatch, secrets=WEDGED)
    rows = pf.servers_requiring_secrets("pmoves_5090_web")
    assert [r["server"] for r in rows] == ["github-official"]


def test_a_secret_ls_failure_is_a_finding_not_an_absence(monkeypatch):
    """`secret ls` failing IS the resolver reporting itself down.

    Docker ran; the answer was "broken". Treating that as unmeasurable would
    downgrade a real finding into a shrug.
    """
    _fake_docker(monkeypatch, secrets=None)
    assert pf.resolver_healthy() is False


def test_a_missing_profile_is_unmeasured_not_a_pass(monkeypatch):
    """Exit 3. The gateway's readiness was never established."""
    _fake_docker(monkeypatch, secrets="NAME\n", profiles="ID\tName\ndefault\tD\n")
    assert pf.main(["--profile", "pmoves_5090_web"]) == 3


def test_no_docker_at_all_is_unmeasured(monkeypatch):
    monkeypatch.setattr(pf.shutil, "which", lambda _: None)
    assert pf.main(["--profile", "pmoves_5090_web"]) == 3


def test_json_mode_says_whether_it_measured(monkeypatch, capsys):
    """Machine-readable callers must be able to tell 3 from 0 without the code."""
    _fake_docker(monkeypatch, secrets="NAME\n", profiles="ID\tName\ndefault\tD\n")
    pf.main(["--profile", "pmoves_5090_web", "--json"])
    import json as _json

    payload = _json.loads(capsys.readouterr().out)
    assert payload["measured"] is False
    assert "not imported" in payload["reason"]


def test_the_listener_actually_invokes_the_preflight():
    """Wiring assertion: a gate nothing calls is decoration.

    The listener is what `make -C pmoves mcp-toolkit-gateway-start` runs, so the
    preflight has to be on that path or it protects nothing.
    """
    body = LISTENER.read_text(encoding="utf-8")
    assert "mcp_toolkit_preflight" in body, (
        "mcp-toolkit-gateway-listen.sh does not call the preflight"
    )
